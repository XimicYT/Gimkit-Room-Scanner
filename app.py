import streamlit as st
import asyncio
import re
import base64
import random
import string
import time
from playwright.sync_api import sync_playwright

# --- CONFIGURATION & UI SETUP ---
st.set_page_config(page_title="Gimkit Lobby Scanner", page_icon="🔍")
st.title("🔍 Gimkit Lobby Scanner")
st.markdown("Enter a Game Code to check the lobby status and player list.")

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
    rand_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    bot_name = f"Scanner_{rand_id}"
    seen_players = set()
    status = "Active"

    with sync_playwright() as p:
        # Headless must be True for cloud hosting
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
            page.goto(f"https://www.gimkit.com/join?gc={code}", timeout=10000)
            time.sleep(1.5)
            
            if page.get_by_text("Game not found").is_visible():
                return "Closed", [], 0
            
            # Attempt to join to trigger the socket
            page.keyboard.press("Tab")
            page.keyboard.type(bot_name)
            page.keyboard.press("Enter")
            
            # Watchdog loop (max 10 seconds)
            start_time = time.time()
            while time.time() - start_time < 10:
                if len(seen_players) > 0:
                    time.sleep(0.3) # User-requested 0.3s burst
                    break
                time.sleep(0.2)
                
        except Exception as e:
            return "Error", [], 0
        finally:
            browser.close()

    final_list = [p for p in seen_players if p != bot_name]
    return "Active", final_list, len(final_list)

# --- EXECUTION ---
if scan_button and game_code:
    with st.spinner(f"Joining {game_code}..."):
        status, players, count = scan_lobby(game_code)
        
    if status == "Closed":
        st.error("❌ Game Not Active (Game not found)")
    elif status == "Error":
        st.warning("⚠️ Connection Error. Try again.")
    else:
        st.success("✅ Lobby Captured!")
        col1, col2 = st.columns(2)
        col1.metric("Room Status", "OPEN")
        col2.metric("Player Count", count)
        
        if players:
            st.write("### 📜 Usernames")
            st.write(", ".join(players))
        else:
            st.info("The room is empty (except for the bot).")