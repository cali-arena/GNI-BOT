# Get changes to Streamlit Cloud

1. **Push the repo that Streamlit Cloud uses**
   - If the app is connected to **cali-arena/GNI-BOT**: push from `GNI-BOT`:
     ```bash
     cd c:\Users\lucas\GNI\GNI-BOT
     git add apps/wa-qr-cloud-ui
     git commit -m "Streamlit: fix WhatsApp Connect, login, api helpers"
     git push origin main
     ```
   - If the app is connected to another repo (e.g. a fork or gni-bot-creator), push from that repo instead.

2. **Streamlit Cloud settings**
   - **Root directory:** `apps/wa-qr-cloud-ui`
   - **Main file path:** `app.py`
   - **Secrets:** `GNI_API_BASE_URL` (required)

3. **After pushing**
   - Open your app on share.streamlit.io → **Manage app** → **Reboot app** (or wait for auto-redeploy).

If you still see SyntaxError after pushing, open **Manage app** → **Logs** and check the full error (file and line number).
