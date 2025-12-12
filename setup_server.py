#!/usr/bin/env python3
"""Script to set up Discord server channels and messages for photo verification."""

import os
import requests
from dotenv import load_dotenv

# Load environment
load_dotenv('/home/metzlerdalton3/bot/discord_ai_photo_bot/.env')

TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GUILD_ID = os.getenv('DISCORD_GUILD_ID')
HEADERS = {
    'Authorization': f'Bot {TOKEN}',
    'Content-Type': 'application/json'
}

def create_channel():
    """Create photo-verification channel under LLAMA LLAMA CLUB category."""
    # Category ID for LLAMA LLAMA CLUB
    category_id = 1448815942435078355

    data = {
        'name': 'photo-verification',
        'type': 0,  # text channel
        'parent_id': str(category_id),
        'topic': 'AI-powered photo verification - upload photos and generate verification images'
    }

    response = requests.post(
        f'https://discord.com/api/v10/guilds/{GUILD_ID}/channels',
        headers=HEADERS,
        json=data
    )

    if response.status_code == 201:
        channel_data = response.json()
        print(f"Created channel: {channel_data['name']} (ID: {channel_data['id']})")
        return channel_data['id']
    elif response.status_code == 400 and 'name' in response.json().get('errors', {}):
        print("Channel already exists")
        # Get existing channel
        channels_response = requests.get(
            f'https://discord.com/api/v10/guilds/{GUILD_ID}/channels',
            headers=HEADERS
        )
        if channels_response.status_code == 200:
            channels = channels_response.json()
            for channel in channels:
                if channel['name'] == 'photo-verification':
                    return channel['id']
    else:
        print(f"Failed to create channel: {response.status_code} {response.text}")
    return None

def post_guide_message(channel_id):
    """Post guide message with button in ai-model-creation channel."""
    # ai-model-creation channel ID
    guide_channel_id = 1448815945563902063

    embed = {
        'title': 'AI Photo Verification',
        'description': 'Click the button below to start the photo verification process. This will guide you through uploading photos and generating AI verification images.',
        'color': 0x00ff00,
        'fields': [
            {
                'name': 'Step-by-Step Process',
                'value': '''1. Click 'Start Photo Verification'
2. Upload 3-5 clear photos of the same person
3. Wait for validation (face detection)
4. Choose your verification action
5. Receive AI-generated verification image''',
                'inline': False
            }
        ],
        'footer': {
            'text': 'All uploads are processed securely and deleted after use.'
        }
    }

    components = [
        {
            'type': 1,  # Action row
            'components': [
                {
                    'type': 2,  # Button
                    'style': 3,  # Success (green)
                    'label': 'Start Photo Verification',
                    'custom_id': 'start_verification'
                }
            ]
        }
    ]

    data = {
        'embeds': [embed],
        'components': components
    }

    response = requests.post(
        f'https://discord.com/api/v10/channels/{guide_channel_id}/messages',
        headers=HEADERS,
        json=data
    )

    if response.status_code == 200:
        print("Posted guide message with button")
    else:
        print(f"Failed to post message: {response.status_code} {response.text}")

def delete_verification_channels():
    """Delete any existing photo-verification channels."""
    response = requests.get(
        f'https://discord.com/api/v10/guilds/{GUILD_ID}/channels',
        headers=HEADERS
    )

    if response.status_code == 200:
        channels = response.json()
        for channel in channels:
            if channel['name'] == 'photo-verification':
                delete_response = requests.delete(
                    f'https://discord.com/api/v10/channels/{channel["id"]}',
                    headers=HEADERS
                )
                if delete_response.status_code == 204:
                    print(f"Deleted channel: {channel['name']} (ID: {channel['id']})")
                else:
                    print(f"Failed to delete channel {channel['id']}: {delete_response.status_code}")

    else:
        print(f"Failed to get channels: {response.status_code}")

def main():
    print("Setting up Discord server for photo verification...")

    # Delete old verification channels
    delete_verification_channels()

    # Post guide message
    post_guide_message(None)

    print("Setup complete!")

if __name__ == '__main__':
    main()