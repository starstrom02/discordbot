import discord
import sqlite3
import random

# Create an instance of a client with the necessary intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.guild_messages = True

client = discord.Client(intents=intents)
client.pending_clear = {} # Added pending_clear as class attribute

import asyncio
import colorsys

async def rainbow_role(role):
    hue = 0
    while True:
        # Convert HSV to RGB (hue cycles through rainbow)
        rgb = colorsys.hsv_to_rgb(hue, 0.8, 0.8)
        # Convert RGB to discord color int
        color = int(rgb[0] * 255) << 16 | int(rgb[1] * 255) << 8 | int(rgb[2] * 255)
        await role.edit(color=color)
        hue = (hue + 0.01) % 1.0
        await asyncio.sleep(5)  # Change color every 5 seconds

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    # Create table if it doesn't exist
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0)''')
    # Add last_daily column if it doesn't exist
    c.execute('''PRAGMA table_info(users)''')
    columns = [col[1] for col in c.fetchall()]
    if 'last_daily' not in columns:
        c.execute('''ALTER TABLE users ADD COLUMN last_daily TEXT DEFAULT NULL''')
    conn.commit()
    conn.close()

# Add points to user
def add_points(user_id, points):
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO users (user_id, points) VALUES (?, COALESCE((SELECT points + ? FROM users WHERE user_id = ?), ?))',
              (user_id, points, user_id, points))
    conn.commit()
    conn.close()

# Get user points
def get_points(user_id):
    conn = sqlite3.connect('economy.db')
    c = conn.cursor()
    c.execute('SELECT points FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

# Event listener for when the bot is ready
@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    print("Bot is ready!")
    init_db()

    # Start rainbow role effect for the specific role
    role_id = 1366047716928520255
    for guild in client.guilds:
        role = guild.get_role(role_id)
        if role:
            try:
                client.loop.create_task(rainbow_role(role))
                print(f"Started rainbow effect for role: {role.name}")
            except Exception as e:
                print(f"Error starting rainbow effect: {str(e)}")
            break

# Store AFK status
afk_users = {}

# Store message history for !gtalk
gtalk_history = []  # [(message, author), ...]
# Store last deleted message
last_deleted = {}  # {channel_id: (content, author, created_at)}
# Store original channel permissions
channel_permissions = {}  # {channel_id: overwrites}

# Event listener for when a message is received
@client.event
async def on_message_delete(message):
    if message.author.bot:
        return
    avatar_url = str(message.author.avatar.url if message.author.avatar else message.author.default_avatar.url)
    last_deleted[message.channel.id] = (message.content, message.author.name, message.created_at, avatar_url, message.author.id)

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # Add random points (1-5) for each message
    if not message.content.startswith('!'):
        points = random.randint(1, 5)
        add_points(message.author.id, points)

    # Points command
    if message.content.lower() == '!shop':
        user_points = get_points(message.author.id)
        embed = discord.Embed(title="🏪 𝓟𝓸𝓲𝓷𝓽𝓼 𝓢𝓱𝓸𝓹", description=f"💰 Your Balance: **{user_points} points**\n\n*Spend your points on exclusive perks!*", color=0x9B59B6)
        embed.add_field(name="1️⃣ 📸 Pic Posting Permission", value="```600 points```\n> Unlock the ability to send pictures in chat!", inline=False)
        embed.add_field(name="2️⃣ 👤 Nickname Change Token", value="```400 points```\n> Change your nickname freely!", inline=False)
        embed.add_field(name="3️⃣ 😎 Custom Emoji Slot", value="```500 points```\n> Submit one emoji suggestion for staff approval!", inline=False)
        embed.add_field(name="4️⃣ 🌟 External Stickers Access", value="```100 points```\n> Use external stickers in the server!", inline=False)
        embed.add_field(name="5️⃣ 👑 Get Admin", value="```1000 points```\n> Gain admin role in the server!", inline=False)
        embed.set_footer(text="💡 Use !buy <item number> to purchase an item")
        await message.channel.send(embed=embed)

    if message.content.lower().startswith('!buy'):
        try:
            item_number = int(message.content.split()[1])
            user_points = get_points(message.author.id)

            items = {
                1: {"name": "📸 Pic Posting Permission", "price": 600, "role_id": 1366438995638091797},
                2: {"name": "👤 Nickname Change Token", "price": 400, "role_id": 1366437312594182315},
                3: {"name": "😎 Custom Emoji Slot", "price": 500, "role_name": "Emoji Suggester"},
                4: {"name": "🌟 External Stickers Access", "price": 100, "role_id": 1366454988263653406},
                5: {"name": "👑 Get Admin", "price": 1000, "role_id": 1366458974584569906}
            }

            if item_number not in items:
                await message.channel.send("Invalid item number! Use !shop to see available items.")
                return

            item = items[item_number]
            if user_points < item["price"]:
                await message.channel.send(f"You don't have enough points! You need {item['price']} points but have {user_points}.")
                return

            # Get role by ID or create if it's the emoji role
            if "role_id" in item:
                role = message.guild.get_role(item["role_id"])
                if not role:
                    await message.channel.send("Error: Role not found!")
                    return
            else:
                role = discord.utils.get(message.guild.roles, name=item["role_name"])
                if not role:
                    role = await message.guild.create_role(name=item["role_name"])

            # Add role to user
            await message.author.add_roles(role)

            # Deduct points
            add_points(message.author.id, -item["price"])

            await message.channel.send(f"Successfully purchased {item['name']}! {item['price']} points have been deducted from your balance.")

        except (IndexError, ValueError):
            await message.channel.send("Please use the format: !buy <item number>")
        except Exception as e:
            await message.channel.send(f"Error processing purchase: {str(e)}")

    if message.content.lower().startswith('!points'):
        target_user = message.author
        if message.mentions:
            target_user = message.mentions[0]

        points = get_points(target_user.id)
        embed = discord.Embed(title="Server Points", color=0x00ff00)
        embed.set_author(name=target_user.display_name, 
                        icon_url=target_user.avatar.url if target_user.avatar else target_user.default_avatar.url)
        embed.add_field(name="Points", value=str(points), inline=True)
        await message.channel.send(embed=embed)

    # Auto-remove AFK when user sends any message
    if message.author.id in afk_users and not message.content.lower().startswith('!afk'):
        del afk_users[message.author.id]
        await message.channel.send(f"Welcome back, {message.author.display_name}!")

    # AFK Commands
    if message.content.lower().startswith('!afk'):
        reason = message.content[5:].strip() or "No reason provided"
        afk_users[message.author.id] = (reason, discord.utils.utcnow())
        await message.channel.send(f"🌙 {message.author.display_name} is now AFK: {reason}")

    # Handle mentions of AFK users
    for mention in message.mentions:
        if mention.id in afk_users:
            reason, timestamp = afk_users[mention.id]
            time_diff = discord.utils.utcnow() - timestamp
            hours = time_diff.total_seconds() // 3600
            minutes = (time_diff.total_seconds() % 3600) // 60
            time_str = f"({int(hours)}h {int(minutes)}m ago)" if hours > 0 else f"({int(minutes)}m ago)"
            await message.channel.send(f"⚠️ {mention.display_name} is AFK: {reason} {time_str}")

    if message.content.lower() == "!snipe":
        channel_id = message.channel.id
        if channel_id in last_deleted:
            content, author_name, timestamp, avatar_url, author_id = last_deleted[channel_id]
            time_diff = discord.utils.utcnow() - timestamp
            minutes = int(time_diff.total_seconds() / 60)
            embed = discord.Embed(description=content, color=0x2f3136)
            embed.set_author(name=author_name, icon_url=avatar_url)
            embed.set_footer(text=f"{minutes}m ago")
            await message.channel.send(embed=embed)
        else:
            await message.channel.send("No recently deleted messages found!")

    if message.content.lower() == "!botr":
        if not message.author.guild_permissions.manage_messages:
            await message.channel.send("You don't have permission to remove bot messages!")
            return

        try:
            # Delete the command message first
            await message.delete()

            def is_bot(m):
                return m.author.bot

            deleted = await message.channel.purge(limit=100, check=is_bot)
            await message.channel.send(f"Removed {len(deleted)} bot messages.", delete_after=3)
        except Exception as e:
            await message.channel.send(f"Error removing bot messages: {str(e)}")

    if message.content.lower().startswith('!pay'):
        try:
            # Check command format
            parts = message.content.split()
            if len(parts) != 3 or not message.mentions:
                await message.channel.send("Usage: !pay @user amount")
                return

            target_user = message.mentions[0]
            amount = int(parts[2])

            # Check if amount is positive
            if amount <= 0:
                await message.channel.send("Amount must be positive!")
                return

            # Check if sender has enough points
            sender_points = get_points(message.author.id)
            if sender_points < amount:
                await message.channel.send(f"You don't have enough points! You have {sender_points} points.")
                return

            # Transfer points
            add_points(message.author.id, -amount)
            add_points(target_user.id, amount)

            embed = discord.Embed(title="💸 Points Transfer", color=0x00FF00)
            embed.add_field(name="From", value=message.author.display_name, inline=True)
            embed.add_field(name="To", value=target_user.display_name, inline=True)
            embed.add_field(name="Amount", value=f"{amount} points", inline=True)
            await message.channel.send(embed=embed)

        except ValueError:
            await message.channel.send("Please enter a valid amount!")
        except Exception as e:
            await message.channel.send(f"Error transferring points: {str(e)}")

    if message.content.lower() == "!help":
        help_text = """
Available commands:
• !shop - View the points shop (💰 Check your balance and available items)
• !daily - Claim your daily reward of 100 points 🎁
• !buy <item number> - Purchase an item from the shop (📦 Items: 1-3)
• !help - Shows this help message
• !points - Check your current server points or other users' points by mentioning them.
• !pay @user amount - Send points to another user
• !cadd channel_name category_name - Creates a new channel in specified category
• !gclear - Clear all messages in the current channel (requires confirmation)
• !gtalk message - Makes the bot say your message (Admin only)
• !gtalk history - Shows recent bot messages
• hi - Bot responds with a greeting
• !afk [reason] - Sets your AFK status
• !snipe - Shows the last deleted message in the channel
• !addr role @member - Adds a role to the mentioned member (Manage Roles permission required)
• !botr - Removes bot messages from the channel (Manage Messages permission required)
• !gamble <amount> - Play blackjack with your points (10-1000 points)
• !ld0 - Unlocks all channels (Manage Channels permission required)
• !ld1 - Locks current channel (Manage Channels permission required)
• !ld2 - Locks all channels (Manage Channels permission required)
        """
        await message.channel.send(help_text)

    if message.content.lower().startswith("!ld"):
        if not message.author.guild_permissions.manage_channels:
            await message.channel.send("You don't have permission to lockdown channels!")
            return

        try:
            level = int(message.content[3:])
            if level not in [0, 1, 2]:
                await message.channel.send("Please use !ld0 to unlock, !ld1 for single channel lock, or !ld2 for all channels lock!")
                return

            locked = level != 0
            embed = discord.Embed(title="🔒 Server Lockdown" if locked else "🔓 Server Unlock", color=0xFF0000 if locked else 0x00FF00)
            embed.set_footer(text=f"{'Locked' if locked else 'Unlocked'} by {message.author.display_name}")

            if level == 1:
                if locked:
                    # Store current permissions before locking
                    channel_permissions[message.channel.id] = message.channel.overwrites
                    new_overwrites = message.channel.overwrites
                    new_overwrites[message.guild.default_role] = discord.PermissionOverwrite(send_messages=False)
                    await message.channel.edit(overwrites=new_overwrites)
                else:
                    # Restore original permissions if they exist
                    original_overwrites = channel_permissions.get(message.channel.id)
                    if original_overwrites:
                        await message.channel.edit(overwrites=original_overwrites)
                        del channel_permissions[message.channel.id]
                    else:
                        # If no stored permissions, just enable sending messages
                        current_overwrites = message.channel.overwrites
                        current_overwrites[message.guild.default_role] = discord.PermissionOverwrite(send_messages=True)
                        await message.channel.edit(overwrites=current_overwrites)

                embed.description = f"This channel has been {'locked down' if locked else 'unlocked'}."
                await message.channel.send(embed=embed)
            else:
                for channel in message.guild.text_channels:
                    if locked:
                        # Store current permissions before locking
                        channel_permissions[channel.id] = channel.overwrites
                        new_overwrites = channel.overwrites
                        new_overwrites[message.guild.default_role] = discord.PermissionOverwrite(send_messages=False)
                        await channel.edit(overwrites=new_overwrites)
                    else:
                        # Restore original permissions if they exist
                        original_overwrites = channel_permissions.get(channel.id)
                        if original_overwrites:
                            await channel.edit(overwrites=original_overwrites)
                            del channel_permissions[channel.id]
                        else:
                            # If no stored permissions, just enable sending messages
                            current_overwrites = channel.overwrites
                            current_overwrites[message.guild.default_role] = discord.PermissionOverwrite(send_messages=True)
                            await channel.edit(overwrites=current_overwrites)

                embed.description = f"All channels have been {'locked down' if locked else 'unlocked'}."
                await message.channel.send(embed=embed)

        except Exception as e:
            await message.channel.send(f"Error during lockdown: {str(e)}")

    if message.content.lower() == "hi":
        await message.channel.send("Hello!")

    if message.content.startswith('!cadd'):
        # Check if user has manage channels permission
        if not message.author.guild_permissions.manage_channels:
            await message.channel.send("You don't have permission to create channels!")
            return

        try:
            # Split the command into parts
            parts = message.content.split(' ', 2)  # Split into 3 parts: !cadd, channel_name, category_name
            if len(parts) < 3:
                await message.channel.send("Please use the format: !cadd channel_name category_name")
                return

            channel_name = parts[1]
            category_name = parts[2]

            # Find the category
            category = discord.utils.get(message.guild.categories, name=category_name)
            if not category:
                await message.channel.send(f"Category '{category_name}' not found!")
                return

            # Create the channel
            await message.guild.create_text_channel(channel_name, category=category)
            await message.channel.send(f"Channel '{channel_name}' created in category '{category_name}'!")

        except Exception as e:
            await message.channel.send(f"Error creating channel: {str(e)}")

    if message.content.lower() == "!gclear":
        if not message.author.guild_permissions.manage_messages:
            await message.channel.send("You don't have permission to clear messages!")
            return

        import time
        current_time = time.time()
        channel_id = message.channel.id
        if channel_id not in client.pending_clear:
            client.pending_clear[channel_id] = current_time
            await message.channel.send("Are you sure you want to clear all messages? Type !gclear again within 30 seconds to confirm.")
            return
        elif current_time - client.pending_clear[channel_id] < 30:
            del client.pending_clear[channel_id]
            try:
                await message.channel.purge(limit=None)
                await message.channel.send("Channel cleared!")
            except Exception as e:
                await message.channel.send(f"Error clearing messages: {str(e)}")
        else:
            await message.channel.send("Confirmation timed out.  Please try again.")


    if message.content.lower().startswith('!addr'):
        # Check if user has manage roles permission
        if not message.author.guild_permissions.manage_roles:
            await message.channel.send("You don't have permission to manage roles!")
            return

        try:
            # Split the command into parts
            parts = message.content.split(' ', 2)  # Split into 3 parts: !addr, role, member
            if len(parts) < 3:
                await message.channel.send("Please use the format: !addr role_name @member")
                return

            role_name = parts[1]
            member_mention = parts[2]

            # Get the role (support both role name and role mention)
            if message.role_mentions:
                role = message.role_mentions[0]
            else:
                role = discord.utils.get(message.guild.roles, name=role_name)
                if not role:
                    # Try case-insensitive search
                    role = discord.utils.find(lambda r: r.name.lower() == role_name.lower(), message.guild.roles)
                if not role:
                    await message.channel.send(f"Role '{role_name}' not found!")
                    return

            # Get the member
            member_id = ''.join(filter(str.isdigit, member_mention))
            member = await message.guild.fetch_member(member_id)
            if not member:
                await message.channel.send("Member not found!")
                return

            # Add the role
            await member.add_roles(role)
            await message.channel.send(f"Added role '{role_name}' to {member.display_name}")

        except Exception as e:
            await message.channel.send(f"Error adding role: {str(e)}")

    if message.content.lower().startswith('!rolec'):
        if not message.author.guild_permissions.manage_roles:
            await message.channel.send("You don't have permission to create roles!")
            return

        try:
            # Split the command into parts
            parts = message.content.split()
            if len(parts) < 2:
                await message.channel.send("Usage: !rolec role_name [color_hex] [position] [permissions]\nPermissions: admin, kick, ban, manage_messages, manage_channels, pictures")
                return

            role_name = parts[1]
            color = discord.Color.default()
            position = 0
            permissions = discord.Permissions()

            # Check for optional color (hex format)
            if len(parts) >= 3 and parts[2].startswith('#'):
                color = discord.Color.from_str(parts[2])

            # Check for optional position
            if len(parts) >= 4 and parts[3].isdigit():
                position = int(parts[3])

            # Check for optional permissions
            if len(parts) >= 5:
                perm_map = {
                    'admin': 'administrator',
                    'kick': 'kick_members',
                    'ban': 'ban_members',
                    'manage_messages': 'manage_messages',
                    'manage_channels': 'manage_channels',
                    'send_messages': 'send_messages',
                    'read_messages': 'read_messages',
                    'read_history': 'read_message_history',
                    'embed_links': 'embed_links',
                    'attach_files': 'attach_files',
                    'mention_everyone': 'mention_everyone',
                    'pictures': 'attach_files'
                }
                for perm in parts[4:]:
                    if perm.lower() in perm_map:
                        setattr(permissions, perm_map[perm.lower()], True)

            # Create the role
            role = await message.guild.create_role(name=role_name, color=color, permissions=permissions)

            # Set position if specified
            if position > 0:
                await role.edit(position=position)

            await message.channel.send(f"Created role '{role_name}' successfully!")

        except Exception as e:
            await message.channel.send(f"Error creating role: {str(e)}")

    if message.content.lower().startswith('!gamble'):
        try:
            parts = message.content.split()
            if len(parts) != 2:
                await message.channel.send("Usage: !gamble <amount>")
                return
                
            bet = int(parts[1])
            if bet < 10:
                await message.channel.send("Minimum bet is 10 points!")
                return
            if bet > 1000:
                await message.channel.send("Maximum bet is 1000 points!")
                return
                
            user_points = get_points(message.author.id)
            if user_points < bet:
                await message.channel.send(f"You don't have enough points! You have {user_points} points.")
                return

            # Card deck setup
            suits = ['♠️', '♥️', '♦️', '♣️']
            ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
            deck = [(rank, suit) for suit in suits for rank in ranks]
            random.shuffle(deck)

            def calculate_hand(hand):
                value = 0
                aces = 0
                for rank, _ in hand:
                    if rank in ['J', 'Q', 'K']:
                        value += 10
                    elif rank == 'A':
                        aces += 1
                    else:
                        value += int(rank)
                for _ in range(aces):
                    if value + 11 <= 21:
                        value += 11
                    else:
                        value += 1
                return value

            def format_hand(hand):
                return ' '.join(f"{rank}{suit}" for rank, suit in hand)

            # Initial deal
            player_hand = [deck.pop(), deck.pop()]
            dealer_hand = [deck.pop(), deck.pop()]
            
            # Show initial hands
            embed = discord.Embed(title="🎰 Blackjack", color=0xFFD700)
            embed.add_field(name="Your Hand", value=f"{format_hand(player_hand)} (Value: {calculate_hand(player_hand)})", inline=False)
            embed.add_field(name="Dealer's Hand", value=f"{dealer_hand[0][0]}{dealer_hand[0][1]} ?️", inline=False)
            game_msg = await message.channel.send(embed=embed)

            # Player's turn
            while calculate_hand(player_hand) < 21:
                hit_msg = await message.channel.send("Would you like to hit (👊) or stand (✋)?")
                await hit_msg.add_reaction('👊')
                await hit_msg.add_reaction('✋')

                def check(reaction, user):
                    return user == message.author and str(reaction.emoji) in ['👊', '✋']

                try:
                    reaction, _ = await client.wait_for('reaction_add', timeout=30.0, check=check)
                    await hit_msg.delete()

                    if str(reaction.emoji) == '👊':
                        player_hand.append(deck.pop())
                        embed = discord.Embed(title="🎰 Blackjack", color=0xFFD700)
                        embed.add_field(name="Your Hand", value=f"{format_hand(player_hand)} (Value: {calculate_hand(player_hand)})", inline=False)
                        embed.add_field(name="Dealer's Hand", value=f"{dealer_hand[0][0]}{dealer_hand[0][1]} ?️", inline=False)
                        await game_msg.edit(embed=embed)
                    else:
                        break
                except asyncio.TimeoutError:
                    await message.channel.send("Game cancelled due to timeout!")
                    return

            player_value = calculate_hand(player_hand)
            if player_value > 21:
                add_points(message.author.id, -bet)
                embed = discord.Embed(title="🎰 Blackjack - You Bust! 💥", color=0xFF0000)
                embed.add_field(name="Your Hand", value=f"{format_hand(player_hand)} (Value: {player_value})", inline=False)
                embed.add_field(name="Dealer's Hand", value=f"{format_hand(dealer_hand)} (Value: {calculate_hand(dealer_hand)})", inline=False)
                embed.add_field(name="Result", value=f"You lost {bet} points!", inline=False)
                await game_msg.edit(embed=embed)
                return

            # Dealer's turn
            while calculate_hand(dealer_hand) < 17:
                dealer_hand.append(deck.pop())

            dealer_value = calculate_hand(dealer_hand)
            embed = discord.Embed(title="🎰 Blackjack - Game Over!", color=0xFFD700)
            embed.add_field(name="Your Hand", value=f"{format_hand(player_hand)} (Value: {player_value})", inline=False)
            embed.add_field(name="Dealer's Hand", value=f"{format_hand(dealer_hand)} (Value: {dealer_value})", inline=False)

            if dealer_value > 21 or player_value > dealer_value:
                winnings = bet * 2
                add_points(message.author.id, bet)
                embed.color = 0x00FF00
                embed.add_field(name="Result", value=f"You won {bet} points! 🎉", inline=False)
            elif player_value < dealer_value:
                add_points(message.author.id, -bet)
                embed.color = 0xFF0000
                embed.add_field(name="Result", value=f"You lost {bet} points! 💔", inline=False)
            else:
                embed.color = 0xFFFF00
                embed.add_field(name="Result", value="It's a tie! 🤝", inline=False)

            await game_msg.edit(embed=embed)

        except Exception as e:
            await message.channel.send(f"Error in blackjack game: {str(e)}")

    if message.content.lower() == '!daily':
        try:
            conn = sqlite3.connect('economy.db')
            c = conn.cursor()
            c.execute('SELECT last_daily FROM users WHERE user_id = ?', (message.author.id,))
            result = c.fetchone()
            
            current_time = discord.utils.utcnow().strftime('%Y-%m-%d')
            
            if result is None or result[0] is None:
                add_points(message.author.id, 100)
                c.execute('UPDATE users SET last_daily = ? WHERE user_id = ?', (current_time, message.author.id))
                conn.commit()
                await message.channel.send(f"🎁 You claimed your daily reward of 100 points!")
            elif result[0] != current_time:
                add_points(message.author.id, 100)
                c.execute('UPDATE users SET last_daily = ? WHERE user_id = ?', (current_time, message.author.id))
                conn.commit()
                await message.channel.send(f"🎁 You claimed your daily reward of 100 points!")
            else:
                await message.channel.send("❌ You've already claimed your daily reward today! Come back tomorrow!")
            
            conn.close()
        except Exception as e:
            await message.channel.send(f"Error processing daily reward: {str(e)}")

    if message.content.lower().startswith('!gtalk'):
        # Check if user has admin permissions
        if not message.author.guild_permissions.administrator:
            await message.channel.send("You don't have permission to use this command!")
            return

        if message.content.lower() == "!gtalk history":
            history_msg = "Recent !gtalk messages:\n" + "\n".join(f"{i+1}. {msg} (by {author})" for i, (msg, author) in enumerate(gtalk_history[-10:]))
            await message.channel.send(history_msg)
            return

        # Get the message after !gtalk
        announcement = message.content[7:].strip()
        if not announcement:
            await message.channel.send("Please provide a message to announce!")
            return

        # Delete the command message
        await message.delete()
        # Send the announcement and store in history with author
        await message.channel.send(announcement)
        gtalk_history.append((announcement, message.author.name))

# Your bot's token (already included)
token = 'MTM2NjIzMzQ2MDA1Mzc3NDQ2Nw.Gs-8GK.aZsUv2N8YBcaJW2_uapjfED6UckeZYJV2_46Ps'

# Keep alive server
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=5000)

def keep_alive():
    server = Thread(target=run)
    server.daemon = True  # This ensures the thread will die when the main program dies
    server.start()
    print("Keep alive server started")

# Start the keep-alive server and run the bot
keep_alive()
client.run(token)