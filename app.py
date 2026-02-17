import streamlit as st
import subprocess
import time
import re
import base64
import random
import string
from playwright.sync_api import sync_playwright

# --- INSTALLER (Runs once per session) ---
@st.cache_resource
def install_dependencies():
    subprocess.run(["playwright", "install", "chromium"])

install_dependencies()

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Gimkit Toolkit", page_icon="🧰", layout="wide")

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🧰 Toolkit")
app_mode = st.sidebar.radio("Select Mode:", ["Gimkit Scanner", "Web Debugger"])
st.sidebar.markdown("---")
st.sidebar.info("Switch modes above to access different tools.")

# ==========================================
# MODE 1: GIMKIT SCANNER
# ==========================================
if app_mode == "Gimkit Scanner":
    st.title("🔍 Gimkit Lobby Scanner")
    st.markdown("Scan a game code to see who is inside.")

    col1, col2 = st.columns([3, 1])
    with col1:
        game_code = st.text_input("Enter Game Code:", placeholder="115257")
    with col2:
        debug_mode = st.checkbox("Show Debug Screenshot", help="See what the bot sees")

    scan_button = st.button("Scan Lobby")
    
    BLOCKLIST = ["correct", "local", "detector", "gui", "variable", "property", "type", "value", "skin", "team", "target", "current", "my", "this", "assignment"]

    def scan_lobby(code, debug=False):
        rand_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        bot_name = f"Scanner_{rand_id}"
        seen_players = set()
        screenshot_bytes = None

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            client = context.new_cdp_session(page)
            client.send("Network.enable")

            def extract_strings(binary_data):
                try:
                    text_soup = binary_data.decode('latin-1')
                    return re.findall(r'[a-zA-Z0-9_\- ]{3,}', text_soup)
                except:
                    return []

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
                
                if debug:
                    screenshot_bytes = page.screenshot()

                if page.get_by_text("Game not found").is_visible():
                    return "Closed", [], 0, screenshot_bytes
                
                page.keyboard.press("Tab")
                page.keyboard.type(bot_name)
                page.keyboard.press("Enter")
                
                start_time = time.time()
                while time.time() - start_time < 8:
                    if len(seen_players) > 0:
                        time.sleep(0.3) 
                        break
                    time.sleep(0.1)
                    
            except Exception:
                return "Error", [], 0, screenshot_bytes
            finally:
                browser.close()

        final_list = [p for p in seen_players if p != bot_name]
        return "Active", final_list, len(final_list), screenshot_bytes

    if scan_button and game_code:
        with st.spinner("🕵️ Scanning room..."):
            status, players, count, debug_image = scan_lobby(game_code, debug_mode)
            
        if debug_image:
            st.image(debug_image, caption="Bot View", use_column_width=True)

        if status == "Closed":
            st.error("❌ Room Closed (Game not found)")
        elif status == "Error":
            st.warning("⚠️ Connection timed out.")
        else:
            st.success(f"✅ Found {count} players!")
            if players:
                st.write(", ".join(players))
            else:
                st.info("Room is empty.")


# ==========================================
# MODE 2: WEB DEBUGGER
# ==========================================
else:
    st.title("📸 Web Debugger")
    st.markdown("Enter any URL to retrieve a screenshot of how the page looks to the bot.")

    url = st.text_input("Enter URL:", placeholder="https://google.com")
    full_page = st.checkbox("Full Page Capture")
    
    if st.button("Take Screenshot"):
        if not url.startswith("http"):
            st.error("URL must start with http:// or https://")
        else:
            with st.spinner("Loading page..."):
                try:
                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=True)
                        page = browser.new_page(viewport={'width': 1280, 'height': 720})
                        page.goto(url, timeout=25000)
                        time.sleep(2) # Wait for render
                        
                        screenshot = page.screenshot(full_page=full_page)
                        browser.close()
                        
                        st.image(screenshot, caption=f"Snapshot of {url}", use_column_width=True)
                        st.download_button("Download Image", screenshot, "debug_snap.png", "image/png")
                        
                except Exception as e:
                    st.error(f"Error: {e}")
