from modules.macro.game_data import (
    questCompleterCollectNames,
    questCompleterFieldNames,
    questCompleterMobNames,
)


class QuestObjectiveMixin:
    def parseQuestObjective(self, objectiveText):
        """
        Parses a raw objective text string into structured data.
        Returns dict with 'action', 'target', and 'quantity' keys.
        """
        import re

        # Clean and normalize the text
        text = objectiveText.lower().strip()

        # Fix common OCR errors
        ocr_fixes = {
            'trom': 'from',
            'completel': 'complete',
            'dippebeams': 'dipper beams',
            'stafi': 'staff',
            'gitts': 'gifts',
            'duped': 'duped',
            'glitched': 'glitched',
            'corrupting': 'corrupting',
            'repairing': 'repairing',
            'robo': 'robo',
            'obtain': 'obtain',
            'fielc': 'field',
            'pamal.ll': 'complete',
            'pumpkirpatch': 'pumpkin patch',
            'red brickfield': 'red brick field',
            'electro-magnet': 'electromagnet',
            'giveto': 'give to',
            'red-cact-rose': 'red-cactus-rose'
        }

        for ocr_error, correction in ocr_fixes.items():
            text = text.replace(ocr_error, correction)

        # Fix number formatting (dots instead of commas)
        # Pattern: number.number.number -> number,number,number
        text = re.sub(r'(\d{1,3})\.(\d{3})\.(\d{3})', r'\1,\2,\3', text)
        # Pattern: number.number -> number,number
        text = re.sub(r'(\d{1,3})\.(\d{3})', r'\1,\2', text)

        # Extract quantity - look for numbers
        quantity = 1  # default
        quantity_match = re.search(r'\b(\d+)\b', text)
        if quantity_match:
            quantity = int(quantity_match.group(1))

        # Define patterns for different action types
        patterns = [
            # Petal token catch patterns (new for petal quests)
            (r'.*\b(catch)\b.*\b(red bloom petals?)\b.*\b(in|from)\b.*\b([a-z ]+?)\b field', 'gatherpetal', r'(clover|spider|bamboo|blue flower|cactus|clover|coconut|dandelion|mountain top|mushroom|pepper|pine tree|pineapple|pumpkin|rose|spider|strawberry|stump|sunflower)'),
            (r'.*\b(catch|collect|get|gather|harvest)\b.*\b((red|blue|white|pink|green|cyan|yellow)\s+)?bloom\s+petals?\b.*\b(in|from)\b.*\b([a-z ]+?)\b field', 'gatherpetal', r'(clover|spider|bamboo|blue flower|cactus|coconut|dandelion|mountain top|mushroom|pepper|pine tree|pineapple|pumpkin|rose|strawberry|stump|sunflower)'),
            # Catch patterns (special catching mechanics)
            (r'.*\b(catch|chase)\b.*', 'catch', r'.*'),
            # Craft patterns (check first - specific crafting actions)
            (r'.*\b(craft|make)\b.*\b(blender|ingredients)\b.*', 'craft', r'.*'),
            # Obtain patterns (specific obtain actions)
            (r'.*\b(obtain|get)\b.*', 'obtain', r'.*'),
            # Challenge patterns (check first - specific mini-games like Ant Challenge)
            (r'.*\b(get|earn|achieve)\b.*\b(score|amulet)\b.*\b(challenge)\b.*', 'challenge', r'.*'),
            # Feed patterns (check first as they have specific targets)
            (r'.*\b(feed|give)\b.*\b(blueberr\w*|strawberr\w*)\b.*', 'feed', r'blueberr\w*|strawberr\w*'),
            # Pollen collection patterns (color-specific pollen)
            (r'.*\b(collect|get)\b.*\b(\d+)\b.*\b(blue|red|white)\b.*\b(pollen)\b.*', 'pollen', r'blue|red|white'),
            # Token patterns
            (r'.*\b(token|ability|boost)\b.*', 'token', r'(blue|red|rage|honey).*?(boost|ability)?|.*?(boost).*?(blue|red)'),
            # Collect patterns (specific collectible items only)
            (r'.*\b(booster|dispenser|machine|printer|stack|clock|stocking|wreath|feast|samovar|snow|art|candle|match|storm)\b.*', 'collect', r'(booster|dispenser|machine|printer|stack|clock|stocking|wreath|feast|samovar|snow|art|candle|match|storm)'),
            # Kill patterns
            (r'.*\b(kill|defeat|destroy|slay)\b.*', 'kill', r'(giant\s+ants?|army\s+ants?|fire\s+ants?|coconut\s+crabs?|mechsquitos?|scorpions?|mantises?|spiders?|beetles?|ladybugs?|rhinobeetles?|ants?|werewolves?|wolves?|king\s+beetles?|tunnel\s+bear)'),
            # Gather patterns (fields/plants) - more flexible to handle OCR errors
            (r'.*\b(gather|collect|get|harvest|pick)\b.*', 'gather', r'(strawberr\w*|blue\s*flower|pine\s*tree|mushroom|rose|clover|bamboo|cactus|pumpkin|pineapple|coconut|dandelion|spider|stump|pepper|mountain\s*top|sunflower|sunflow\w*|pineappl\w*)'),
            # Fallback patterns
            (r'.*\b(blueberr\w*|strawberr\w*)\b.*', 'fieldtoken', r'blueberr\w*|strawberr\w*'),
            (r'.*\b(coconut\s+crabs?|mechsquitos?|scorpions?|mantises?|spiders?|beetles?|ladybugs?|rhinobeetles?|ants?|werewolves?|wolves?|tunnel\s+bear)\b.*', 'kill', r'coconut\s+crabs?|mechsquitos?|scorpions?|mantises?|spiders?|beetles?|ladybugs?|rhinobeetles?|ants?|werewolves?|wolves?|tunnel\s+bear'),
            (r'.*', 'unknown', r'.*')  # Default fallback changed from 'gather' to 'unknown'
        ]

        action = None
        target = text

        for pattern, action_type, target_pattern in patterns:
            if re.search(pattern, text):
                action = action_type
                # Extract target using the target pattern
                target_match = re.search(target_pattern, text)
                if target_match:
                    target = target_match.group(0).strip()
                break

        # Normalize target names
        target = re.sub(r'[^\w\s]', '', target).strip()
        target = re.sub(r'\s+', '_', target)

        # Remove action words from target
        action_words = ['use', 'collect', 'get', 'from', 'gather', 'kill', 'defeat', 'destroy', 'feed', 'give', 'to', 'bee']
        for word in action_words:
            target = re.sub(r'\b' + word + r'\b', '', target).strip()
        # Remove numbers from target (quantities shouldn't be part of the target name)
        target = re.sub(r'\b\d+\b', '', target).strip()
        target = re.sub(r'_+', '_', target).strip('_')  # Clean up extra underscores

        # Handle common plural forms and normalize names
        plural_to_singular = {
            'strawberries': 'strawberry',
            'blue_flowers': 'blue_flower',
            'pine_trees': 'pine_tree',
            'mushrooms': 'mushroom',
            'roses': 'rose',
            'clovers': 'clover',
            'cactuses': 'cactus',
            'cacti': 'cactus',
            'pumpkins': 'pumpkin',
            'pineapples': 'pineapple',
            'coconuts': 'coconut',
            'dandelions': 'dandelion',
            'spiders': 'spider',
            'stumps': 'stump',
            'peppers': 'pepper',
            'blueberries': 'blueberry',
            'scorpions': 'scorpion',
            'mantises': 'mantis',
            'beetles': 'beetle',
            'ladybugs': 'ladybug',
            'ants': 'ant',
            'werewolves': 'werewolf',
            'wolves': 'werewolf',
            'coconut_crabs': 'coconut_crab',
            'coconut_crab': 'coconut_crab',
            'mechsquitos': 'mechsquito',
            'mechsquito': 'mechsquito',
            # OCR error corrections
            'sunflowefield': 'sunflower',
            'sunflow': 'sunflower',
            'pineapplpatch': 'pineapple',
            'pineappl': 'pineapple',
            'pumpkirpatch': 'pumpkin',
            'coconucrab': 'coconut_crab',
            'coconutcrab': 'coconut_crab',
            'coconut_crabs': 'coconut_crab'
        }

        target = plural_to_singular.get(target, target)

        # For collect actions, normalize to standard names
        if action == 'collect':
            collect_mappings = {
                'blue_booster': 'blue_booster',
                'red_booster': 'red_booster',
                'mountain_booster': 'mountain_booster',
                'sticker_printer': 'sticker_printer',
                'sticker_stack': 'sticker_stack',
                'blueberry_dispenser': 'blueberry_dispenser',
                'strawberry_dispenser': 'strawberry_dispenser',
                'coconut_dispenser': 'coconut_dispenser',
                'royal_jelly_dispenser': 'royal_jelly_dispenser',
                'treat_dispenser': 'treat_dispenser',
                'ant_pass_dispenser': 'ant_pass_dispenser',
                'buy_ant_pass': 'buy_ant_pass',
                'glue_dispenser': 'glue_dispenser',
                'wealth_clock': 'wealth_clock',
                'stockings': 'stockings',
                'wreath': 'wreath',
                'feast': 'feast',
                'samovar': 'samovar',
                'snow_machine': 'snow_machine',
                'lid_art': 'lid_art',
                'candles': 'candles',
                'memory_match': 'memory_match',
                'mega_memory_match': 'mega_memory_match',
                'extreme_memory_match': 'extreme_memory_match',
                'winter_memory_match': 'winter_memory_match',
                'honey_storm': 'honeystorm'
            }
            # Try to match the target to known collect items
            for key in collect_mappings:
                if key.replace('_', '') in target.replace('_', ''):
                    target = key
                    break

        # For feed actions, extract just the berry type
        if action == 'feed':
            if 'blueberr' in target:
                target = 'blueberry'
            elif 'strawberr' in target:
                target = 'strawberry'

        # For token actions, simplify target
        if action == 'token':
            # Check for boost tokens first
            if 'boost' in text:
                if 'blue' in target:
                    target = 'blueboost'
                elif 'red' in target:
                    target = 'redboost'
            elif 'blue' in target and 'boost' in text:
                target = 'blueboost'
            elif 'red' in target and 'boost' in text:
                target = 'redboost'
            elif 'blue' in target:
                target = 'blue'
            elif 'red' in target:
                target = 'red'

        return {
            'action': action,
            'target': target,
            'quantity': quantity
        }

    def mapObjectiveToMacroAction(self, parsedObjective, originalText=""):
        """
        Maps a parsed objective to macro action format.
        Returns a list of action strings compatible with the existing task system.
        """
        action = parsedObjective['action']
        target = parsedObjective['target']
        quantity = parsedObjective['quantity']
        text = originalText  # For checking original text content

        # Special handling for petal quests
        if action == 'gatherpetal':
            # Try to extract the field from the text or target
            field = None
            # If the regex matched, target should be the field name
            if target:
                field = target.replace(' ', '_').lower()
            else:
                # Fallback: try to extract from text
                import re
                m = re.search(r'in the ([a-z ]+?) field', text)
                if m:
                    field = m.group(1).replace(' ', '_').lower()
            if field:
                return [f"gatherpetal_{field}"]
            else:
                return []

        if 'sticker stack badge' in text.lower():
            return []  # Sticker stack badges are not collect_stack
        if 'ultimate ant annihilation' in text.lower():
            return []  # Quest title, not a task
        if 'complete' in text.lower():
            return []  # Skip completed tasks

        # Normalize target names using the mapping dictionaries
        normalizedTarget = target

        if action == 'gather':
            normalizedTarget = questCompleterFieldNames.get(target, target)
        elif action == 'kill':
            normalizedTarget = questCompleterMobNames.get(target, target)
        elif action == 'collect':
            normalizedTarget = questCompleterCollectNames.get(target, target)
        elif action == 'feed':
            # For feed actions, normalize to singular forms
            if 'blueberr' in target:
                normalizedTarget = 'blueberry'
            elif 'strawberr' in target:
                normalizedTarget = 'strawberry'
            elif 'sunflower' in target and 'seed' in target:
                normalizedTarget = 'sunflower_seed'
            elif 'treat' in target:
                normalizedTarget = 'treat'
            elif 'pineapple' in target:
                normalizedTarget = 'pineapple'
            elif 'moon' in target and 'charm' in target:
                normalizedTarget = 'moon_charm'
            else:
                normalizedTarget = target

        # Special handling for different action types
        if action == 'gather':
            # Handle goo collection from specific colors or fields
            if 'goo' in text.lower():
                if 'red' in text.lower():
                    # "Collect X goo from red flowers" → gather from red fields
                    return ['gather_red']  # Gather from red fields for goo
                elif 'blue' in text.lower():
                    return ['gather_blue']  # Gather from blue fields for goo
                elif 'stump' in text.lower():
                    return ['gather_stump']  # Gather from stump field for goo
                # Add other field-specific goo handling as needed

            # Only allow valid field names for gathering
            validFields = ['pineapple', 'pumpkin', 'rose', 'cactus', 'pepper', 'strawberry', 'blue flower',
                          'sunflower', 'dandelion', 'mushroom', 'clover', 'bamboo', 'spider', 'stump',
                          'pine tree', 'mountain top', 'coconut']
            # Fallback: extract field from text when target parsing fails (e.g., pollen from field)
            import re
            field_match = re.search(
                r'\b(strawberr\w*|blue\s*flower|pine\s*tree|mushroom|rose|clover|bamboo|cactus|pumpkin|'
                r'pineappl\w*|pineapple|coconut|dandelion|spider|stump|pepper|mountain\s*top|sunflow\w*)\b',
                text.lower()
            )
            if field_match:
                field_raw = field_match.group(0).strip()
                if field_raw.startswith('strawberr'):
                    field_raw = 'strawberry'
                elif field_raw.startswith('pineappl'):
                    field_raw = 'pineapple'
                elif field_raw.startswith('sunflow'):
                    field_raw = 'sunflower'
                normalizedField = questCompleterFieldNames.get(field_raw, field_raw)
                if normalizedField in validFields:
                    return [f"gather_{normalizedField}"]
            if normalizedTarget.endswith('_field'):
                normalizedTarget = normalizedTarget[:-6]
            if normalizedTarget in validFields:
                # These are field names that can be gathered
                return [f"gather_{normalizedTarget}"]
            else:
                # Skip other gather actions (tool-based, malformed, etc.)
                return []

        elif action == 'kill':
            # Filter out unsupported boss mobs
            if 'king' in text.lower() and 'beetle' in normalizedTarget:
                return ['kill_king_beetle']  # Add King Beetle to priority tasks
            if 'tunnel_bear' in normalizedTarget:
                return ['kill_tunnel_bear']  # Add Tunnel Bear to priority tasks
            if 'vicious' in text.lower() and 'bee' in normalizedTarget:
                return ['stinger_hunt']
            else:
                # Format: kill_mob (macro handles quantity internally)
                return [f"kill_{normalizedTarget}"]

        elif action == 'collect':
            # Format: collect_item
            return [f"collect_{normalizedTarget}"]

        elif action == 'feed':
            # Format: feed_quantity_item (quantity is often * for unlimited)
            if quantity > 1:
                return [f"feed_{quantity}_{normalizedTarget}"]
            else:
                return [f"feed_*_{normalizedTarget}"]

        elif action == 'token':
            # Token collection is not supported - filter out
            return []

        elif action == 'pollen':
            # Handle pollen collection by color
            if 'blue' in target.lower():
                return ['pollen_blue']
            elif 'red' in target.lower():
                return ['pollen_red']
            elif 'white' in target.lower():
                return ['pollen_white']
            else:
                return [f"pollen_{normalizedTarget}"]

        elif action == 'pollengoo':
            # Handle pollen goo actions
            if 'blue' in target.lower():
                return ['pollengoo_blue']
            elif 'red' in target.lower():
                return ['pollengoo_red']
            else:
                return [f"pollengoo_{normalizedTarget}"]

        elif action == 'fieldtoken':
            # Handle field token actions
            if 'blueberry' in target.lower():
                return ['fieldtoken_blueberry']
            elif 'strawberry' in target.lower():
                return ['fieldtoken_strawberry']
            else:
                return [f"fieldtoken_{normalizedTarget}"]

        # Special mob handling
        elif action == 'kill' and 'vicious' in target:
            # "Defeat X Vicious Bees" → Use stinger hunt
            return ['stinger_hunt']

        elif action == 'feed':
            # Feed actions → Use feedBee method
            if quantity > 1:
                return [f"feed_bee_{quantity}_{normalizedTarget}"]
            else:
                return [f"feed_bee_{normalizedTarget}"]

        elif action == 'gather' and 'planter' in target:
            # "Collect X Tokens from Planters" → Use planter placement
            return ['planters']

        elif action == 'craft':
            # Only allow craft actions with specific context (ingredients, blender, etc.)
            if 'ingredient' in target.lower() or 'blender' in target.lower():
                return ['craft']
            else:
                # Generic "craft" without context - skip
                return []

        elif action == 'obtain':
            # Obtain actions → Mark as unsupported for now
            return []  # Don't add unsupported tasks

        elif action == 'catch':
            # Catch actions → Mark as unsupported for now
            return []  # Don't add unsupported tasks

        elif action == 'unknown':
            # Unknown actions → Don't add to queue
            return []

        else:
            # For other actions, only add if they look like valid macro tasks
            task = f"{action}_{normalizedTarget}"
            # Filter out malformed tasks, completed tasks, token tasks, and tool-based tasks
            if (len(task) > 50 or '_' not in task or task.count('_') > 3 or
                'complete' in task or task.startswith('token_') or
                '_with_' in task):
                return []  # Skip malformed/completed/token/tool-based tasks
            return [task]
