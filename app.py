import streamlit as st
import asyncio
import re
import base64
import random
import string
import time
import os
import subprocess
from playwright.sync_api import sync_playwright

# --- CRITICAL FIX FOR STREAMLIT CLOUD ---
# This ensures Chromium is actually installed on the server
@st.cache_resource
def install_browser():
    # Only runs once per session deployment
    subprocess.run(["playwright", "install", "chromium"])

install_browser()
# ----------------------------------------

st.set_page_config(page_title="Gimkit Scanner", page_icon="🔍")
st.title("🔍 Gimkit Lobby Scanner")

game_code = st.text_input("Enter Game Code:", placeholder="115257")
scan_button = st.button("Scan Lobby")

BLOCKLIST = ["correct", "local", "detector", "gui", "variable", "property", "type", "value", "skin", "team", "target", "current", "my", "this", "assignment"]

def extract_strings(binary_data):
    try:
        text_soup = binary_data.decode('latin-1')
        return re.findall(r'[a-zA-Z0-9_\- ]{3,}', text_soup)
    except:
        return []

def scan_lobby(code):
    # Generates a name like Scanner_X92J to avoid 'taken' errors
    rand_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    bot_name = f"Scanner_{rand_id}"
    seen_players = set()

    with sync_playwright() as p:
        # headless=True is mandatory for the web
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        client = context.new_cdp_session(page)
        client.send("Network.enable")

        def on_frame(params):
            try:
                payload = params['response']['payloadData']
                opcode = params['response'].get('opcode', 1)
                raw_bytes = payload.encode('utf-8') if opcode == 1 else base64.b64decode(payload)
                words = extract_strings(raw_bytes)
                for i in range(1, len(words)):
                    if words[i].strip() == "player":
                        name = words[i-1].replace('"', '').strip()
                        if not any(bad in name.lower() for bad in BLOCKLIST) and 2 <= len(name) <= 20:
                            seen_players.add(name)
            except:
                pass

        client.on("Network.webSocketFrameReceived", on_frame)
        
        try:
            page.goto(f"https://www.gimkit.com/join?gc={code}", timeout=15000)
            time.sleep(1)
            
            if page.get_by_text("Game not found").is_visible():
                return "Closed", [], 0
            
            # Type and Enter
            page.keyboard.press("Tab")
            page.keyboard.type(bot_name)
            page.keyboard.press("Enter")
            
            # Watchdog: Wait for first name, then 0.3s burst
            start_time = time.time()
            while time.time() - start_time < 8: # 8s max wait
                if len(seen_players) > 0:
                    time.sleep(0.3) 
                    break
                time.sleep(0.1)
                
        except Exception:
            return "Error", [], 0
        finally:
            browser.close()

    # Filter out our unique bot name
    final_list = [p for p in seen_players if p != bot_name]
    return "Active", final_list, len(final_list)

if scan_button and game_code:
    with st.spinner("🕵️ Stepping into the lobby..."):
        status, players, count = scan_lobby(game_code)
        
    if status == "Closed":
        st.error("❌ Room Closed (Game not found)")
    elif status == "Error":
        st.warning("⚠️ Connection timed out. The room might be dead.")
    else:
        st.balloons()
        st.success(f"✅ Found {count} players!")
        
        st.metric(label="Room Status", value="OPEN")
        
        if players:
            st.subheader("📜 Player List")
            # Displays as a clean, searchable list
            st.write(", ".join(players))
        else:
            st.info("The lobby is currently empty.")
