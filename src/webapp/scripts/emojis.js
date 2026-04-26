/*
=============================================
Emoji list
=============================================
*/


//utility function to convert them to an array
function toEmojiArray(emojiObj){
    out = []
    for (const [k,v] of Object.entries(emojiObj)) {
        out.push(`${v} ${toTitleCase(k.replaceAll("_"," "))}`)
    }
    return out
}

//same as toEmojiArray, but for images
//if v is null, no img is made
//if right is true, image appears on the right of text
function toImgArray(emojiObj, right = false){
    out = []
    for (const [k,v] of Object.entries(emojiObj)) {
        const imgHTML = v? `<img src="./assets/icons/${v}.png" class="icon-img">`: ''
        const text = toTitleCase(k.replaceAll("_"," "))
        out.push( right? `${text}${imgHTML}`: `${imgHTML}${text}`)
    }
    return out
}

//https://emojidb.org/
const fieldEmojis = {
    sunflower: "🌻",
    dandelion: "🌼",
    mushroom: "🍄",
    blue_flower: "🔷",
    clover: "🍀",
    strawberry: "🍓",
    spider: "🕸️",
    bamboo: "🐼",
    pineapple: "🍍",
    stump: "🐌",
    cactus: "🌵",
    pumpkin: "🎃",
    pine_tree: "🌲",
    rose: "🌹",
    mountain_top: "⛰️",
    pepper: "🌶️",
    coconut: "🥥",
    hive_hub: "🏠"
}

const collectEmojis = {
    wealth_clock: "🕒",
    blueberry_dispenser: "🔵",
    strawberry_dispenser: "🍓",
    coconut_dispenser: "🥥",
    royal_jelly_dispenser: "💎",
    treat_dispenser: "🦴",
    ant_pass_dispenser: "🎫",
    glue_dispenser: "🧴",
    stockings: "🧦",
    feast: "🍽️",
    samovar: "🏺",
    snow_machine: "❄️",
    lid_art: "🖼️",
    candles: "🕯️",
    wreath: "🎄",
    sticker_printer: "🖨️",
    mondo_buff: "🐣",
    memory_match: "🍍",
    mega_memory_match: "🌟",
    extreme_memory_match: "🌶️",
    winter_memory_match: "❄️",
    honeystorm: "🟧",
    Auto_Field_Boost: "🎲"
    

}

const killEmojis = {
    stinger_hunt: "😈",
    scorpion: "",
    werewolf: "",
    ladybug: "",
    rhinobeetle: "",
    spider: "",
    mantis: "",
    ant_challenge: "🎯",
    coconut_crab: "",
    king_beetle: "",
    tunnel_bear: "",
    stump_snail: "🐌",
}

const nectarIcons = {
    comforting: "comforting",
    motivating: "motivating",
    satisfying: "satisfying",
    refreshing: "refreshing",
    invigorating: "invigorating"
}
const fieldNectarIcons = {
    none: null,
    sunflower: "satisfying",
    dandelion: "comforting",
    mushroom: "motivating",
    blue_flower: "refreshing",
    clover: "invigorating",
    strawberry: "refreshing",
    spider: "motivating",
    bamboo: "comforting",
    pineapple: "satisfying",
    stump: "motivating",
    cactus: "invigorating",
    pumpkin: "satisfying",
    pine_tree: "comforting",
    rose: "motivating",
    mountain_top: "invigorating",
    pepper: "invigorating",
    coconut: "refreshing"
}

const planterIcons = {
    none: null,
    paper: "paper_planter",
    ticket: "ticket_planter",
    festive: "festive_planter",
    sticker: "sticker_planter",
    plastic: "plastic_planter",
    candy: "candy_planter",
    red_clay: "red_clay_planter",
    blue_clay: "blue_clay_planter",
    tacky: "tacky_planter",
    pesticide: "pesticide_planter",
    'heat-treated': "heat-treated_planter",
    hydroponic: "hydroponic_planter",
    petal: "petal_planter",
    planter_of_plenty: "planter_of_plenty_planter"
}

const blenderIcons = {
    none: null,
    red_extract: "red_extract",
    blue_extract: "blue_extract",
    enzymes: "enzymes",
    oil: "oil",
    glue: "glue",
    tropical_drink: "tropical_drink",
    gumdrops: "gumdrops",
    moon_charm: "moon_charm",
    glitter: "glitter",
    star_jelly: "star_jelly",
    purple_potion: "purple_potion",
    soft_wax: "soft_wax",
    hard_wax: "hard_wax",
    swirled_wax: "swirled_wax",
    caustic_wax: "caustic_wax",
    field_dice: "field_dice",
    smooth_dice: "smooth_dice",
    loaded_dice: "loaded_dice",
    super_smoothie: "super_smoothie",
    turpentine: "turpentine"
}

const fieldBoosterEmojis = {
    blue_booster: "🔵",
    red_booster: "🔴",
    mountain_booster: "⚪"
}

const stickerStackIcon = {
    sticker_stack: "sticker_stack"
}

const questGiverEmojis = {
    polar_bear_quest: "🐻‍❄️",
    brown_bear_quest: "🐻",
    honey_bee_quest: "🐝",
    bucko_bee_quest: "💙",
    riley_bee_quest: "❤️",
    black_bear_quest: "🐻"
}

const diceIcons = {
    field_dice: "field_dice",
    smooth_dice: "smooth_dice",
    loaded_dice: "loaded_dice"
}
