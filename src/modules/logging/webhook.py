from discord_webhook import DiscordEmbed, DiscordWebhook
from modules.misc.formatting import timestampedEmbedText
from modules.misc.settingsManager import getMacroVersion

# Global variable to store message ID for pinning
last_message_id = None
last_channel_id = None


def response_footer():
    return f"Fuzzy Macro - Version {getMacroVersion()}"

def webhook(url, title, desc, time, color, imagePath = None, ping_user_id = None, time_format=24, fields = None):
    global last_message_id, last_channel_id

    # Check if URL is provided
    if not url or not url.strip():
        print(f"Warning: Webhook URL is empty. Skipping webhook message: {title} {desc}")
        return None

    webhook = DiscordWebhook(url = url,rate_limit_retry=True)

    # Add ping if user ID is provided
    if ping_user_id:
        webhook.content = f"<@{ping_user_id}>"

    embedTitle, embedDesc = timestampedEmbedText(title, desc, time, time_format)
    embed = DiscordEmbed(title=embedTitle, description=embedDesc, color=color)
    embed.set_footer(text=response_footer())

    # Add embed fields (for hourly/session report text summaries)
    if fields:
        for f in fields:
            embed.add_embed_field(name=f["name"], value=f["value"], inline=f.get("inline", False))

    try:
        #if to add image
        if imagePath:
            with open(imagePath, "rb") as f:
                webhook.add_file(file=f.read(), filename= "screenshot.png")
            embed.set_image(url='attachment://screenshot.png')
        # add embed object to webhook
        webhook.add_embed(embed)
        response = webhook.execute()
        # Store message ID and channel ID for potential pinning
        if response and hasattr(response, 'json'):
            response_data = response.json()
            last_message_id = response_data.get('id')
            last_channel_id = response_data.get('channel_id')
        return response
    except Exception as e:
        print(f"Webhook Error: {e}")
        return None
