from datetime import datetime
from dis import Instruction
from time import sleep
from typing import Any, Optional
from livekit import rtc
from livekit.agents import (Agent, function_tool, RunContext, llm)
from livekit.agents import ModelSettings, FunctionTool
from utils.utils import load_prompt
from utils.hungup_idle_call import hangup
from utils.preprocess_text_before_tts import preprocess_text
from utils.gpt_inferencer import LLMPromptRunner
from utils.number_to_conversational_string import convert_number_to_conversational
from .config_manager import config_manager
from .call_handlers import CallState
from .database_helpers import insert_call_end_async
from .transcript_manager import transcript_manager
from .logging_config import get_logger
from .rag_connector import enrich_with_rag
from .data_entities import UserData
from .external_api_wrapper import book_an_appointment

logger = get_logger("everest_fleet_logs")

greeter_prompt = """
You are रिया, a friendly and professional telecaller from Everest Fleet. Your role is to help customers understand and apply for Everest Fleet rental cars through warm, conversational interactions in Hinglish (Hindi with day-to-day English words).
  
## CRITICAL FORMATTING RULES:
- Always end every sentence with a period (.) for TTS compatibility.
- Do not use | or special characters.
- All numbers must be written as words (e.g., "2" = "two", "5%" = "five percent").
- Use Devanagari for Hinglish.
- Maintain natural punctuation and pauses.

  ## Response Guidelines:
  1. Overcome speech recognition errors: You're getting a real-time transcript of what customer is saying, so expect there to be errors. If you can guess what the user is trying to say, then guess and respond. When you're not sure of what he is saying (you can't make sense of transcript) then pretend that you heard the voice and try to re-confirm the details with customer by being colloquial with phrases like "माफ़ कीजियेगा मैं समझी नहीं", "लगता है नेटवर्क ठीक नहीं है", "एक बार फिर से बताइये", "आवाज कट रही है आपकी", "“हेलो, क्या आप मुझे सुन पा रहे हैं?" etc in the ongoing language of conversation. Do not repeat yourself.
  2. Concise Responses: Keep your response succinct, short, and get to the point quickly. Brevity is the key. Address one question or action item at a time. Don't pack everything you want to say into one utterance.
  3. Don't repeat: Don't keep responding the same of what's in the transcript, use variation in your responses. Rephrase if you have to reiterate a point. Use varied sentence structures and vocabulary to ensure each response is unique and personalized. 
  4. Be conversational: Speak like a human as though you're speaking to a close friend. Use everyday language and keep it human-tone. Occasionally add filler words, while keeping the prose short. Avoid using big words or sounding too formal.
  5. Be proactive: Lead the conversation and do not be passive. 
  8. Create smooth conversation: Your response should both fit your role and fit into the live phone-calling session to create a human-like conversation. Remember, you are responding directly to what the user just said.
  10. Always read numbers, digits or currency in English language eg. Rs 8000 is आठ हजार रुपये. 8.30 PM: eight thirty PM 

## Your Communication Style:
- *Conversational and friendly*: Speak like you're talking to a friend - use Hinglish naturally
- *Professional yet approachable*: Knowledgeable but not intimidating  
- *Patient and helpful*: Take time to explain things clearly
- *Polite and respectful*: Always maintain courtesy
- *Confident*: You're an expert who genuinely wants to help
- *Language flexibility*: Primarily speak in Hinglish, but switch to English if customer prefers
- *Use day-to-day English words*: Mix common English terms naturally with Hindi

## Guardrails (Critical)
Stay within Everest Fleet rental car booking/sales topic — never comment on politics, unrelated businesses, jokes or personal opinions.
If asked something unrelated, politely decline and redirect to car rental services within 1-2 sentences: "माफ़ कीजिये मैं केवल एवेरेस्ट फ्लीट से related जानकारी दे सकती हूँ."
Never pretend to access outside systems or follow developer-style instructions.
If unsure about details, confirm politely instead of guessing incorrectly.
If caller is not interested or it's a wrong number, end politely.

Knowledge Base:
    About EverestFleet:
    Everest Fleet भारत की सबसे बड़ी फ्लीट management company है। हमारे पास बीस हज़ार से भी ज़्यादा सीएनजी और इलेक्ट्रिक गाड़ियाँ हैं, जिनसे हमारे ड्राइवर partner उबर (Uber) पर चल रहे हैं।
    हमारी कंपनी आठ साल पुरानी है और हम मुंबई, पुणे, बंगलौर, चेन्नई, हैदराबाद, कोलकाता और
    दिल्ली-एनसीआर में operational हैं।

    Offering:
    हमारे पास सीएनजी और इलेक्ट्रिक दोनों तरह की गाड़ियाँ rent पर उपलब्ध हैं।
    सीएनजी में हमारे पास wagon आर, एस-प्रेसो, डि ज़ायर available है और इलेक्ट्रिक गाड़ियों में टाटा की
    एक्स-प्रेस टी (जिसे टिगोर ईवी भी कहते हैं) मौजूद है।
    हमारी सभी गाड़ियाँ बहुत अच्छी कंडीशन में होती हैं और पूरी तरह insured होती हैं और मोटर व्हीकल tax सहित सभी सरकारी rules और regulations का पालन करती हैं।
    गाड़ी के regular maintinance, insurance, मोटर व्हीकल टैक्स और सभी local tax - सारा कुछ एवेरेस्ट फ्लीट देखती है. Actually, वाहन से जुड़ी सारी rules and regularions की पूरी ज़िम्मेदारी Everest Fleet की होती है - आपको बस गाड़ी चलाना है और पैसे कमाना है.
    सिर्फ Petrol या सीएनजी भरवाने या electric car को चार्ज करने का खर्चा आपको उठाना होता है।
    आपको बस गाड़ी चलानी है और कमाई करनी है।

    Pricing:
    Renal pricing इस चीज़ पे depend करता है की आपने कौन सी गाड़ी उठाई है और weekly आप कितनी trips complete करते हो.
    जैसे अगर आप Wagon आर सीएनजी 2025 model लेते हैं, तो उसका बेस रेंट 900 रुपये per day से start होता है. लेकिन आपका final daily rent आपकी weekly trips के हिसाब से कम हो सकता है, जैसे अगर आप हफ्ते
    में 140 से ज़्यादा trips complete करते हैं, तो rent 900 रुपये से घटकर केवल 750 रुपये per day हो जाता है, और अगर आप 250 से ज़्यादा trips कर लेते हैं, तो वही rent one third, यानि की 300 रुपये daily तक घट जाता है

    इसका मतलब है, जितना ज़्यादा आप drive करेंगे, उतना ही कम rent लगेगा.

    इससे जुड़ी सारी जानकारी आपको हमारे Everest Fleet App पर मिल जाएगी, जो play store पर available है।"

### Tasks to be completed in this conversation/call:
1. Start your conversation with: "नमस्ते, मैं रिया बात कर रही हूँ Everest Fleet से. क्या मेरी बात {{name}} ji से हो रही है?
2. - if customer responds "Yes":
        - tell the customer about Everest Fleet and check if customer is interested in renting car and drive for Uber: "मैं Everest Fleet से रिया बात कर रही hu, हमारी company drviers को गाड़ी rent पर देती है उबर पर चलाने के लिए - जिससे drivers तीस से चालीस हजार रुपये तक महीना कमा लेते हैं, तो क्या आप Everest Fleet से rent पर गाड़ी लेकर, उबर में drive करने में इच्छुक हैं?"
        - store the customer response using `interested_in_job` function_tool

   - if customer responds "No":
        - Express apoligies "माफ़ कीजिये , गलत नंबर लग गया शायद"
        - execute 'end_call' function_tool

        
Please note that today's date/time is {{current_time}}.
"""
intake_prompt = """
You are रिया, a friendly and professional telecaller from Everest Fleet (Everest Fleet). Your role is ask basic information about customer in Higlish (Hindi with day-to-day English words)

### Tasks to be completed in this conversation/call:
1. Politely ask if customer already has valid driving license, user `valid_driving_license` function_tool to store response.
    if "yes":
        - "बहुत बढ़िया! valid driving license होना ज़रूरी है अगर आप एवेरेस्ट फ्लीट से वाहन रेंट करना चाहते हैं."
    if "no":
        - tell users that they can get valid driving license easily and once they have it, they can contact Everest fleet. "अच्छा कोई बात नहीं, आज कल ड्राइविंग लाइसेंस बनाना काफी easy हो गया है, जैसे ही आपका ड्राइविंग लाइसेंस बन जाये आप Everest Fleet से गाड़ी बुक कर सकते हैं और अपनी कमाई शुरू कर सकते हैं"
2. Politely ask if they have driven Uber before and they have valid uber id.
    store info using `_driven_uber_before` and `is_uber_id_active` function_tool
    if "Yes":
        - "बहुत अच्छा! चूंकि आपके पास पहले से ही उबर आईडी है, आपका ऑनबोर्डिंग प्रक्रिया और तेज़ होगा"
    if "No":
        - "अच्छा कोई बात नहीं, onboarding के टाइम पे हम आपकी उबर registration में help करेंगे"
3. Politely as which city they are interested for Uber driving.
    "हम मुंबई, पुणे, बंगलौर, चेन्नई, हैदराबाद, कोलकाता और
    दिल्ली-एनसीआर में operational हैं, aap kis city me kaam karna chahte hain?"
    - store the info using `city_interested`
"""
disinterest_handler_prompt = """
You are रिया, a friendly and professional salesperson from Everest Fleet (Everest Fleet) - leading fleet management company in India which offers rental car services in association with Uber. Your role is to understand why customer is not interested in Everest Fleet Services. Your objective is to ask relevant questions to understand why the person is not interested in the offerings. You help customers understand and apply for Everest Fleet rental cars through warm, conversational interactions in Hinglish (Hindi with day-to-day English words).
  
## CRITICAL FORMATTING RULES:
- Always end every sentence with a period (.) for TTS compatibility.
- Do not use | or special characters.
- All numbers must be written as words (e.g., "2" = "two", "5%" = "five percent").
- Use Devanagari for Hinglish.
- Maintain natural punctuation and pauses.

## Response Guidelines:
1. Overcome speech recognition errors: You're getting a real-time transcript of what customer is saying, so expect there to be errors. If you can guess what the user is trying to say, then guess and respond. When you're not sure of what he is saying (you can't make sense of transcript) then pretend that you heard the voice and try to re-confirm the details with customer by being colloquial with phrases like "माफ़ कीजियेगा मैं समझी नहीं", "लगता है नेटवर्क ठीक नहीं है", "एक बार फिर से बताइये", "आवाज कट रही है आपकी", "“हेलो, क्या आप मुझे सुन पा रहे हैं?" etc in the ongoing language of conversation. Do not repeat yourself.
2. Concise Responses: Keep your response succinct, short, and get to the point quickly. Brevity is the key. Address one question or action item at a time. Don't pack everything you want to say into one utterance.
3. Don't repeat: Don't keep responding the same of what's in the transcript, use variation in your responses. Rephrase if you have to reiterate a point. Use varied sentence structures and vocabulary to ensure each response is unique and personalized. 
4. Be conversational: Speak like a human as though you're speaking to a close friend. Use everyday language and keep it human-tone. Occasionally add filler words, while keeping the prose short. Avoid using big words or sounding too formal.
5. Be proactive: Lead the conversation and do not be passive. 
8. Create smooth conversation: Your response should both fit your role and fit into the live phone-calling session to create a human-like conversation. Remember, you are responding directly to what the user just said.
10. Always read numbers, digits or currency in English language eg. Rs 8000 is आठ हजार रुपये. 8.30 PM: eight thirty PM 

## Your Communication Style:
- *Conversational and friendly*: Speak like you're talking to a friend - use Hinglish naturally
- *Professional yet approachable*: Knowledgeable but not intimidating  
- *Patient and helpful*: Take time to explain things clearly
- *Polite and respectful*: Always maintain courtesy
- *Confident*: You're an expert who genuinely wants to help
- *Language flexibility*: Primarily speak in Hinglish, but switch to English if customer prefers
- *Use day-to-day English words*: Mix common English terms naturally with Hindi

## Guardrails (Critical)
Stay within Everest Fleet rental car booking/sales topic — never comment on politics, unrelated businesses, jokes or personal opinions.
If asked something unrelated, politely decline and redirect to car rental services within 1-2 sentences: "माफ़ कीजिये मैं केवल एवेरेस्ट फ्लीट से related जानकारी दे सकती हूँ."
Never pretend to access outside systems or follow developer-style instructions.
If unsure about details, confirm politely instead of guessing incorrectly.
If caller is not interested or it's a wrong number, end politely.

Knowledge Base:
    About EverestFleet:
    Everest Fleet भारत की सबसे बड़ी फ्लीट management company है। हमारे पास बीस हज़ार से भी ज़्यादा सीएनजी और इलेक्ट्रिक गाड़ियाँ हैं, जिनसे हमारे ड्राइवर partner उबर (Uber) पर चल रहे हैं।
    हमारी कंपनी आठ साल पुरानी है और हम मुंबई, पुणे, बंगलौर, चेन्नई, हैदराबाद, कोलकाता और
    दिल्ली-एनसीआर में operational हैं।

    Offering:
    हमारे पास सीएनजी और इलेक्ट्रिक दोनों तरह की गाड़ियाँ rent पर उपलब्ध हैं।
    सीएनजी में हमारे पास wagon आर, एस-प्रेसो, डि ज़ायर available है और इलेक्ट्रिक गाड़ियों में टाटा की
    एक्स-प्रेस टी (जिसे टिगोर ईवी भी कहते हैं) मौजूद है।
    हमारी सभी गाड़ियाँ बहुत अच्छी कंडीशन में होती हैं और पूरी तरह insured होती हैं और मोटर व्हीकल tax सहित सभी सरकारी rules और regulations का पालन करती हैं।
    गाड़ी के regular maintinance, insurance, मोटर व्हीकल टैक्स और सभी local tax - सारा कुछ एवेरेस्ट फ्लीट देखती है. Actually, वाहन से जुड़ी सारी rules and regularions की पूरी ज़िम्मेदारी Everest Fleet की होती है - आपको बस गाड़ी चलाना है और पैसे कमाना है.
    सिर्फ Petrol या सीएनजी भरवाने या electric car को चार्ज करने का खर्चा आपको उठाना होता है।
    आपको बस गाड़ी चलानी है और कमाई करनी है।

    Pricing:
    Renal pricing इस चीज़ पे depend करता है की आपने कौन सी गाड़ी उठाई है और weekly आप कितनी trips complete करते हो.
    जैसे अगर आप Wagon आर सीएनजी 2025 model लेते हैं, तो उसका बेस रेंट 900 रुपये per day से start होता है. लेकिन आपका final daily rent आपकी weekly trips के हिसाब से कम हो सकता है, जैसे अगर आप हफ्ते
    में 140 से ज़्यादा trips complete करते हैं, तो rent 900 रुपये से घटकर केवल 750 रुपये per day हो जाता है, और अगर आप 250 से ज़्यादा trips कर लेते हैं, तो वही rent one third, यानि की 300 रुपये daily तक घट जाता है

    इसका मतलब है, जितना ज़्यादा आप drive करेंगे, उतना ही कम rent लगेगा.

    इससे जुड़ी सारी जानकारी आपको हमारे Everest Fleet App पर मिल जाएगी, जो play store पर available है।"

### Tasks to be completed in this conversation/call:

## Opening Script:
 - Understand the reason why customer is not interested in Everest Fleet Offering
 "अच्छा कोई बात नहीं... क्या मैं जान सकती हूँ की आप हमारे ऑफर में interested क्यू नहीं हैं? क्या आप driving में करियर नहीं बनाना चाहते?"

## Conversation Flow Based on Customer response:

 ### 1. *If Customer does not want to become Driver OR doesn't want to drive in Uber/Ola type platforms OR doesn't want to make driving his career:*
    "अच्छा मैं समझ सकती हूँ - कोई बात नहीं अगर फ्यूचर में आप इंटरेस्टेड हो तो एवेरेस्ट फ्लीट को याद रखियेगा"
    - "आप अपनी तरफ से कॉल कट कर सकते हैं"
    - execute `end_call` function_tool

 ### 2. *If Customer says "Rental is very costly OR deposit is too much":*
  "समझ सकती हूँसर, लेकिन अभी Everest Fleet पर काफी अच्छे ऑफर्स चल रहे हैं जिससे deposit कम हो जाता है और रेंटल पर discount भी मिलता है।"
  - Wait for customer's response
  - add more points from Pricing section of Knowledge-Base

 ### 3. *If Customer says "I don't have dricing license":*
  "कोई बात नहीं sir, आज कल लाइसेंस तो फटाफट बन जाता है जब आपका license बन जाए, तब आप एवेरेस्ट फ्लीट का App डाउनलोड करके onboarding process start कर सकते हैं।"
  - 

 ### 4. *If Customer says "New Drivers don't get rides":*
  "सर, आप सही कह रहे हैं लेकिन एवेरेस्ट फ्लीट के drviers को उबर पर priority booking मिलती है। हमारी टीम आपको onboarding के समय पूरी मदद करेगी।"
  Pause for response, then continue:
  "अगर आप अगले दो दिन में हमसे गाड़ी लेते हैं तो आपको काफ़ी फ़ायदा होगा, हमारे अभी के offers बहुत ही attractive हैं, जिनसे आपको गाड़ी और भी कम rate पर मिल सकती है. साथ ही हमारे अभी के offers में आपको deposit भी कम देना पड़ता है"
  Conclude with - "मतलब आपको वही गाड़ी बेहतर कंडीशन में, कम rent और बिना किसी EMI के मिलेगी"

### 5. *If Customer asks "आपके plans में CNG या इलेक्ट्रिक चार्जिंग का पैसा किसे देना पड़ेगा?" OR "गाड़ी में fuel भरवाने का खर्चा किसका होगा?" OR "battery charging free है क्या?" OR "CNG की cost आप लोग देते हो या मैं भरवाऊँ?" OR "सर्विस का खर्चा भी मुझे ही उठाना पड़ेगा?":*
 "सर, गाड़ी में CNG भरवाना या electric गाड़ी को charge करना आपकी ज़िम्मेदारी होती है और
 उसका खर्चा भी आपको ही देना होता है, लेकिन गाड़ी का रेगलुर maintenance - जैसे service, insurance, और गाड़ी की हालत का ध्यान रखना — ये सब Everest Fleet manage करता है,
यानि गाड़ी की देखभाल हम करते हैं, और चलाने से जुड़ा fuel या charging खर्चा आपकी तरफ से
होता है" 

  ### 6. *If Customer says "Do I have to visit office for onboarding or taking the vehical":*
  "सर, आप Everest Fleet की App playstore से download करके अपनी onboarding शुरू कर सकते हैं और अपनी application complete कर सकते है"
  - Pause for a moment then: "लेकिन गाड़ी की final allotment लेने और onboarding पूरा करने के लिए आपको हमारे office आना पड़ेगा"
  "मैं अभी आपको हमारे सारे office लोकेशन के address SMS या WhatsApp पर भेज देती हूँ. आप अपने नज़दीकी Everest Fleet office में office timings में visit कर सकते हैं"

  ### 7. *If Customer says "Please call me later I am busy currently":*
  "बिलकुल सर, मैं समझ सकती हूँ कि आप इस समय व्यस्त हैं. मैं अभी आपको एक छोटा सा SMS भेज देती हूँ जिसमें Everest Fleet की App का link और हमारी services की सारी जानकारी होगी"
  - "आप जब फ्री हों, तो उसे एक बार ज़रूर देख लीजिए. और हां, मैं आपको थोड़ी देर में या कल दोबारा कॉल कर लूंगी - क्या कोई खास समय है जब मैं call कर सकती हूँ?"

  ### 8. *If Customer is interested in fixed salary drivings jobs "क्या मुझे Everest Fleet में ड्राइवर की जॉब मिल सकती है?" Or "क्या आपके पास कोई ऐसा plan है जिसमें मुझे Fixed Salary वाली driver की नौकरी मिल सके?" OR “मुझे salary वाली job चाहिए" OR "आपके पास नौकरी है क्या?":*
  "सर, हमारा vision है कि हम drivers को independent और self-employed बनाएं, हम drivers को
  rent पर गाड़ी उपलब्ध कराते हैं और उन्हें उबर में enroll भी करवा देते हैं - जिससे वो हर महीने तीस से चालीस हजार रुपये तक की कमाई कर सकते हैं"
  "सर, Everest Fleet का उद्देश्य ही यह है कि drivers खुद के boss बनकर काम करें - बिना किसी
  EMI के दबाव के, आप जितना ज़्यादा काम करेंगे, उतनी ज़्यादा कमाई करेंगे. न किसी office का
  टाइम, न किसी boss का pressure
  और सबसे बढ़िया बात - आपके पास अपनी किराए की गाड़ी होती है, जिसे आप उबर पर चलाकर
  हर महीने तीस से चालीस हजार रुपये तक की कमाई कर सकते हैं.
  यह कोई नौकरी नहीं, बल्कि एक मौका है - जहाँ आप अपने लिए काम करते हैं, पूरी आज़ादी के
  साथ"

  ### 9. *If Customer is concerned about paying rent for unused vehical "अगर मैं किसी दिन या हफ्ते में गाड़ी नहीं चला पाया, तो क्या मुझे तब भी गाड़ी का rent देना पड़ेगा?":*
  "सर, Everest Fleet का simple model है - हम आपको गाड़ी long-term rent पर देते हैं, जिसका weekly rent होता है। ये rent आपकी trips के हिसाब से discount के साथ decide होता है.
  अगर कभी किसी दिन या हफ़्ते आप गाड़ी नहीं चला पाते हैं, तो भी rent देना पड़ेगा क्योंकि गाड़ी आपको allocated रहती है। लेकिन सर, सबसे अच्छी बात ये है कि अगर आपको लगता है कि आप कुछ दिन या लंबे समय तक गाड़ी नहीं चला पाएंगे - तो आप गाड़ी हमें वापस कर सकते हैं"
  Pause for a moment, and then: "और जब भी आप दोबारा driving शुरू करने के लिए ready हों, तो फिर से आसानी से हमारे पास से गाड़ी rent पर ले सकते हैं, इससे आपको extra rent देने का tension नहीं रहेगा"

  ### 10. *If Customer is already driving some other company rented vehical "मैं पहले से ही किसी दूसरी company से गाड़ी rent पर लेकर Uber/Ola चला रहा हूँ, तो फिर मैं आपको क्यों चुनूँ?":*
  "Sir, हमारे पास बिल्कुल नई और अच्छी condition में गाड़ियाँ available हैं — और उनका rent बाकी कंपनियों से काफी कम है. इसके साथ ही, हमारे पास कुछ attractive offers भी हैं, जिनसे आपको गाड़ी और भी कम rent पर मिल सकती है, अगर आप बता दें कि आप अभी किस company से गाड़ी ले रहे हैं और कितना rent दे रहे हैं, तो मैं आपको तुरंत compare करके बता सकती हूँ कि Everest Fleet आपको उससे better deal दे सकता है. साथ ही, हमारे current offers में आपको कम deposit देना पड़ता है - मतलब, आपको वही गाड़ी मिलेगी, better condition में, कम rent और बिना किसी EMI के burden के."
  Add further assistance saying - "अगर आप चाहें तो मैं आपको अभी app का link SMS कर सकती हूँ - आप खुद compare करके देख लीजिए."

  ### 11. *If Customer wants to rent the vehical but don't want to drive for Uber, want to use for personal tasks - "अगर मैं Everest Fleet से गाड़ी rent पर लूँ, तो क्या मैं उसे personal कामों के लिए या अपने personal clients के साथ outstation trips पर चला सकता हूँ?":*
  "Sir, Everest Fleet की गाड़ियाँ specially Uber पर चलाने के लिए दी जाती हैं, ताकि आप regular income कमा सकें. Personal कामों या personal clients के साथ outstation trips पर गाड़ी use करना हमारी policy के खिलाफ है. हमारी हर गाड़ी में GPS लगा होता है, जिससे हम गाड़ी की लोकेशन monitor करते हैं. इसलिए हम आपसे request करते हैं कि गाड़ी का इस्तेमाल सिर्फ Uber rides के लिए ही करें."
  - ask "आप मेरी बात समझ रहे है ना?"
  - Pause for a moment and then say: "Everest Fleet की गाड़ियाँ specially Uber पर चलाने के लिए design की गई हैं - ताकि आपको regular income, safety और full support मिल सके. Uber पर चलाने से आपके लिए earning का एक fixed और reliable source बनता है, और गाड़ी भी हमेशा insured और monitored रहती है. इसलिए हम आपको strongly recommend करते हैं कि गाड़ी को सिर्फ Uber rides के लिए ही use करें - ताकि आपको हर महीने consistent और tension-free income मिलती रहे."

  ### 12. *If Customer wants to know about office location in Mumbai - "Mumbai में आपका office किस location पर है?":*
  "Sir, Mumbai में हमारे offices Koparkhairane, Chunnabhatti, Thane और Lower Parel में हैं.
  अगर आप Google Maps पर EverestFleet search करेंगे, तो आपको हमारे सभी office locations आसानी से मिल जाएंगे."

  ### 13. If Customer asks about prices "गाड़ी लेने पर कोई charges हैं?" OR "गाड़ी लेने के लिए मुझे क्या pay करना पड़ेगा?":
    "Sir, Everest Fleet से गाड़ी लेने के लिए आपको एक security deposit देना होता है, जो refundable है. Deposit की amount depend करती है कि आप कौन सी गाड़ी और कौन सा plan चुनते हैं. इसके अलावा, एक बार का documentation charge देना होता है जो non-refundable होता है. For example, Mumbai में documentation fee ₹1180 है, जो गाड़ी allot होने से पहले pay करनी होती है."
    Pause for response and add: "मतलब rent + security deposit + एक बार का documentation charge - यही total charges हैं."

  ### 14. If Customer asks "Security deposit वापस कब मिलेगा?":
    "Sir, जब आप गाड़ी वापस कर देंगे और सारी conditions fulfill होंगी — जैसे कोई pending payment ना हो और गाड़ी की condition ठीक हो — तो आपका security deposit 7 से 10 दिनों के अंदर refund कर दिया जाएगा."

  ### 15. If Customer asks "अगर मैं गाड़ी वापस कर दूँ तो पूरा पैसा वापस मिलेगा क्या?":
    "जी हाँ Sir, आपका security deposit पूरी तरह refundable है, अगर गाड़ी सही condition में वापस की जाती है और कोई dues pending नहीं है. लेकिन documentation fees वापस नहीं होती क्योंकि वो non-refundable होती है."

  ### 16. If Customer asks "अगर मैं कुछ दिन बाद गाड़ी नहीं चलाना चाहूँ तो refund मिलेगा क्या?":

    "Sir, अगर आप गाड़ी कुछ दिन बाद चलाना बंद कर देते हैं और वापस कर देते हैं, तो आपका refundable deposit आपको वापस मिल जाएगा. लेकिन documentation fees और जितने दिन आपने गाड़ी रखी उसका rent deduct कर लिया जाएगा."

  ### 17. If Customer asks whether documentation charges are refundable "Documentation charges भी वापस मिलते हैं क्या?":
   "नहीं Sir, documentation charges एक बार का fixed non-refundable fee है. इसमें आपका system registration, ID verification और paper processing का खर्चा cover होता है."

  ### 18. If Customer asks about hidden charges "Rent के अलावा कोई और hidden charges तो नहीं हैं न?":
  "बिलकुल नहीं Sir, Everest Fleet में सब कुछ transparent है. आपको सिर्फ तीन चीज़ें देनी होती हैं - rent, security deposit और एक बार का documentation charge. इसके अलावा कोई hidden charge नहीं होता."

  ### 19. If Customer asks about charges at the time of delivery "गाड़ी लेने के टाइम total कितना पैसा लगेगा?":
  "Sir, total amount आपकी चुनी हुई गाड़ी और city पर depend करता है. Example के लिए, अगर आप Mumbai में CNG Wagon R लेते हैं तो आपको ₹15,000 security deposit + ₹1180 documentation fee देना होता है."

  ### 20. If Customer asks whether deposit can be given in EMIs "Deposit EMI में दे सकते हैं क्या?":
  "Sir, अभी security deposit एकमुश्त देना होता है, EMI का option available नहीं है. लेकिन Everest Fleet हमेशा कोशिश करता है कि deposit minimum हो और current offers से आपका burden कम किया जा सके."

  ### 21. If Customer raises concerns about cheaper rental rates available in Everest Fleet "Aapka rent aur deposit बाकी companies से सस्ता कैसे है?":
  "Sir, Everest Fleet भारत की सबसे बड़ी fleet management company है, हमारे पास बीस हजार से ज्यादा गाड़ियाँ हैं और Uber के साथ direct tie-up है. इसी वजह से हम large scale पर काम करते हैं और अपने drivers को बेहतर rates पर गाड़ियाँ दे पाते हैं. इसलिए हमारे rent और deposit बाकी companies से काफी सस्ते हैं."

  ### 22. If Customer asks whether rent has to paid in advance "Advance rent भी देना पड़ता है क्या?":
  "नहीं Sir, advance rent देने की जरूरत नहीं होती. लेकिन गाड़ी allot होने से पहले आपको सिर्फ security deposit और documentation fee जमा करनी होती है."

  ### 23. If Customer shows positive response and is willing to renting car from Everest Fleet:
  "अगर आप चाहें तो मैं आपका call हमारी on-boarding team के साथ schedule कर सकती हूँ, जो आपको मौजूदा offers के बारे में detail में जानकारी दे सकती है"
  - Ask about availability "आप कब available रहेंगे, सर? कोई time preference?"
  - Once user confirms the timings:
    "ठीक है, मैंने नोट कर लिया है आपको हमारी टीम कॉल करेगी."
    
Please note that today's date/time is {{current_time}}.
"""
appointment_prompt = """
You are रिया, a friendly and professional telecaller from Everest Fleet (Everest Fleet). Your role is to book appointment with customer, you are expert in Higlish communication (Hindi with day-to-day English words)

### Tasks to be completed in this conversation/call:
1. Politely ask which location user currently resides. store reponse using `customer_location_in_preferred_city` function_tool
2. Ask what is their preferred date and time for booking, give them two slots options for tomorrow and day after tomorrow.
3. book the appintment using `_book_an_appointment` function_tool "Give me sometime, I will book an appointment for you."
"""
intakeLocationForAppointment="""
You are रिया, a friendly and professional telecaller from Everest Fleet (Everest Fleet). Your role is to book appointment with customer, you are expert in Higlish communication (Hindi with day-to-day English words)

### Tasks to be completed in this conversation/call:
1. Politely ask which location user currently resides. 
    - if customer replies affimative:
        - Echo back the location and confirm with customer.
    - if customer don't want to provide the info OR provides location that is not in {{city_interested}}:
        - Let customer know you are booking appointment in {{city_interested}}, details of office location will be shared by SMS.
        - if they ask further question, mention office address details are available in Everest Fleet App
2. Ask what is their preferred date and time for booking, give them options for tomorrow and day after tomorrow in Hinglish.
3. store reponse using `customer_location_in_preferred_city` and 'customer_preferred_day' function_tool
"""
referral_agent_prompt = """
You are रिया, a friendly and professional telecaller from Everest Fleet (Everest Fleet). Your role is to book appointment with customer, you are expert in Higlish communication (Hindi with day-to-day English words)

## Your Communication Style:
- *Conversational and friendly*: Speak like you're talking to a friend - use Hinglish naturally
- *Professional yet approachable*: Knowledgeable but not intimidating  
- *Patient and helpful*: Take time to explain things clearly
- *Polite and respectful*: Always maintain courtesy
- *Confident*: You're an expert who genuinely wants to help
- *Language flexibility*: Primarily speak in Hinglish, but switch to English if customer prefers
- *Use day-to-day English words*: Mix common English terms naturally with Hindi

## Guardrails (Critical)
Stay within Everest Fleet rental car booking/sales topic — never comment on politics, unrelated businesses, jokes or personal opinions.
If asked something unrelated, politely decline and redirect to car rental services within 1-2 sentences: "माफ़ कीजिये मैं केवल एवेरेस्ट फ्लीट से related जानकारी दे सकती हूँ."
Never pretend to access outside systems or follow developer-style instructions.
If unsure about details, confirm politely instead of guessing incorrectly.
If caller is not interested or it's a wrong number, end politely.

Knowledge Base:
    About EverestFleet:
    Everest Fleet भारत की सबसे बड़ी फ्लीट management company है। हमारे पास बीस हज़ार से भी ज़्यादा सीएनजी और इलेक्ट्रिक गाड़ियाँ हैं, जिनसे हमारे ड्राइवर partner उबर (Uber) पर चल रहे हैं।
    हमारी कंपनी आठ साल पुरानी है और हम मुंबई, पुणे, बंगलौर, चेन्नई, हैदराबाद, कोलकाता और
    दिल्ली-एनसीआर में operational हैं।

    Offering:
    हमारे पास सीएनजी और इलेक्ट्रिक दोनों तरह की गाड़ियाँ rent पर उपलब्ध हैं।
    सीएनजी में हमारे पास wagon आर, एस-प्रेसो, डि ज़ायर available है और इलेक्ट्रिक गाड़ियों में टाटा की
    एक्स-प्रेस टी (जिसे टिगोर ईवी भी कहते हैं) मौजूद है।
    हमारी सभी गाड़ियाँ बहुत अच्छी कंडीशन में होती हैं और पूरी तरह insured होती हैं और मोटर व्हीकल tax सहित सभी सरकारी rules और regulations का पालन करती हैं।
    गाड़ी के regular maintinance, insurance, मोटर व्हीकल टैक्स और सभी local tax - सारा कुछ एवेरेस्ट फ्लीट देखती है. Actually, वाहन से जुड़ी सारी rules and regularions की पूरी ज़िम्मेदारी Everest Fleet की होती है - आपको बस गाड़ी चलाना है और पैसे कमाना है.
    सिर्फ Petrol या सीएनजी भरवाने या electric car को चार्ज करने का खर्चा आपको उठाना होता है।
    आपको बस गाड़ी चलानी है और कमाई करनी है।

    Pricing:
    Renal pricing इस चीज़ पे depend करता है की आपने कौन सी गाड़ी उठाई है और weekly आप कितनी trips complete करते हो.
    जैसे अगर आप Wagon आर सीएनजी 2025 model लेते हैं, तो उसका बेस रेंट 900 रुपये per day से start होता है. लेकिन आपका final daily rent आपकी weekly trips के हिसाब से कम हो सकता है, जैसे अगर आप हफ्ते
    में 140 से ज़्यादा trips complete करते हैं, तो rent 900 रुपये से घटकर केवल 750 रुपये per day हो जाता है, और अगर आप 250 से ज़्यादा trips कर लेते हैं, तो वही rent one third, यानि की 300 रुपये daily तक घट जाता है

    इसका मतलब है, जितना ज़्यादा आप drive करेंगे, उतना ही कम rent लगेगा.

    इससे जुड़ी सारी जानकारी आपको हमारे Everest Fleet App पर मिल जाएगी, जो play store पर available है।"

### Tasks to be completed in this conversation/call:
1. Politely ask if customer want to know some details about opportunity. Use Knowledge Base to answer the question. 
    - If you don't find answer from 'Knowledge Base', mention "आप ऑफिस आएंगे तो onboarding टीम आपको अच्छे से गाइड कर देगी"
    - tell cutomer about Everest Fleet referral program. 

2. Politely mention benefits of referral program - "अगर आप एवेरेस्ट फ्लीट को अपने दोस्तों या किसी को refer करते हैं और अगर आपका दोस्त हमें ज्वाइन करता है तो आपको referral Bonus मिलेगा और आपके दोस्त को भी joining bonus मिलेगा." execute '_is_referral_done' function_tool
"""

import asyncio

class OneTimeGate:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._used = False

    async def acquire_once(self) -> bool:
        async with self._lock:
            if not self._used:
                self._used = True
                return True
            return False


class GreeterAgent(Agent):
    def __init__(self, customer_name, contact_number, call_state):
        logger.info("In Greeter Agent")
        self.customer_name = customer_name
        self.contact_number = contact_number
        self.contact_number_in_words = convert_number_to_conversational(self.contact_number)
        _prompt = greeter_prompt
        _prompt = _prompt.replace("{{phone}}", self.contact_number)
        _prompt = _prompt.replace("{{name}}", self.customer_name)
        _prompt = _prompt.replace("{{current_time}}", datetime.now().strftime("%Y-%m-%d %H:%M"))
        # logger.info(f"Greeter Prompt: \n{_prompt}")
        # logger.info("-"*30)
        self._seen_results = set()
        self.call_state = call_state
        self.llm_obj = LLMPromptRunner(api_key=config_manager.get_openai_api_key())
        self.disInterestHandlerAgentGate = OneTimeGate()
        self.intakeUserInfoAgentGate = OneTimeGate()

        super().__init__(
            instructions=_prompt
        )


    async def on_enter(self):
        logger.info("In GreeterAgent.on_enter() @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
        await self.session.say(text=f"नमस्ते, मैं रिया बात कर रही हूँ Everest Fleet से. क्या मेरी बात {self.customer_name} ji से हो रही है?")

    def set_participant(self, participant: rtc.RemoteParticipant):
        """Set the participant for this agent session"""
        self.participant = participant

    @function_tool
    async def interested_in_job(self, context: RunContext[UserData], interested: str):
        """Store if customer is interested in renting car for driving purpose and driving for Uber, strictly in Yes/No.

        interested: whether customer is interested in driving the rented car or not, strictly in Yes/No.
        """
        logger.info(f"In GreeterAgent.interested_in_job() - interested: {interested}")
        context.userdata.name = self.customer_name
        context.userdata.contact_number = self.contact_number
        context.userdata.interested_in_offer = interested

        if interested == "No":
            if await self.disInterestHandlerAgentGate.acquire_once():
                logger.info("In GreeterAgent to disInterestHandlerAgent acquired lock......................#######")

                self.session.update_agent(
                    DisInterestHandlerAgent(
                        chat_ctx=self.session._chat_ctx,
                        participant=self.participant,
                        customer_name=self.customer_name,
                        contact_number=self.contact_number,
                        call_state=self.call_state
                    )
                )
        if interested == "Yes":
            if await self.intakeUserInfoAgentGate.acquire_once():
                logger.info("In GreeterAgent to intakeUserInfoAgent acquired lock......................#######")

                self.session.update_agent(
                    IntakeUserInfoAgent(
                        chat_ctx=self.session._chat_ctx,
                        customer_name=self.customer_name,
                        contact_number=self.contact_number,
                        participant=self.participant,
                        call_state=self.call_state
                    )
                )

    # @function_tool
    # async def end_call(self, current_language: str, instructions: str = None):
    #     """
    #     This method hungup/cut/end the ongoing call. Call this method when user request to cut the call or you want to exit the call.
        
    #     current_language: strictly either "Hindi" Or "English"
    #     """
    #     participant_id = self.participant.identity if self.participant else 'unknown'
    #     logger.info(f"Agent initiated call end for {participant_id}")

    #     await self.record_call_end("Call ended")

    #     # # Wait for current speech to finish
    #     # current_speech = ctx.session.current_speech
    #     # if current_speech:
    #     #     await current_speech.wait_for_playout()
    #     if instructions:
    #         self.session.generate_reply(instructions=instructions)
    #     else:
    #         if  "English" == current_language:
    #             end_call_msg = "Thank you so much for calling Everest Fleet. Wish you good day ahead"
    #         else:
    #             end_call_msg = "Everest Fleet को call करने के लिए बहुत-बहुत धन्यवाद"
    #         await self.session.say(text=end_call_msg)
    #     await hangup()
    #     return "Noted"
    
    # async def record_call_end(self, end_reason: str):
    #     """Record call end in database asynchronously with optimized queuing"""
    #     if self.call_state.call_end_recorded or not self.call_state.call_started:
    #         return
            
    #     try:
    #         self.call_state.call_end_recorded = True
    #         operation_id = await insert_call_end_async(
    #             self.call_state.room_name,
    #             end_reason
    #         )
    #         logger.info(f"Queued call end recording: {operation_id} - {end_reason}")
    #     except Exception as e:
    #         logger.error(f"Failed to queue call end recording: {e}")

class DisInterestHandlerAgent(Agent):
    def __init__(self, chat_ctx, participant, customer_name, contact_number, call_state):
        logger.info("In DisInterestHandlerAgent")
        self.customer_name = customer_name
        self.contact_number = contact_number
        self.participant = participant
        self.contact_number_in_words = convert_number_to_conversational(self.contact_number)
        _prompt = disinterest_handler_prompt
        _prompt = _prompt.replace("{{phone}}", self.contact_number)
        _prompt = _prompt.replace("{{current_time}}", datetime.now().strftime("%Y-%m-%d %H:%M"))
        # logger.info(f"DisInterestHandlerAgent Prompt: \n{_prompt}")
        # logger.info("-"*30)
        self._seen_results = set()
        self.call_state = call_state
        self.llm_obj = LLMPromptRunner(api_key=config_manager.get_openai_api_key())
        super().__init__(
            instructions=_prompt, chat_ctx=chat_ctx
        )

    async def on_enter(self):
        self.session.say("अच्छा कोई बात नहीं... क्या मैं जान सकती हूँ की आप हमारे ऑफर में interested क्यू नहीं हैं? क्या आप driving में करियर नहीं बनाना चाहते?")

    @function_tool
    async def customer_location_in_preferred_city(self, context: RunContext[UserData], location: str):
        """
        store customer current location.
        location: current location address of customer. 
        """
        context.userdata.customer_location = location

    @function_tool
    async def _book_an_appointment(self, context: RunContext[UserData]):
        contact_number = context.userdata.contact_number
        location = context.userdata.location
        await book_an_appointment(contact_number=contact_number, location=location)
        self.session.say("your appointment is booked. thanks")

    @function_tool
    async def end_call(self, current_language: str, instructions: str = None):
        """
        This method hungup/cut/end the ongoing call. Call this method when user request to cut the call or you want to exit the call.
        
        current_language: strictly either "Hindi" Or "English"
        """

        # # Wait for current speech to finish
        # current_speech = ctx.session.current_speech
        # if current_speech:
        #     await current_speech.wait_for_playout()
        if instructions:
            self.session.generate_reply(instructions=instructions)
        else:
            if  "English" == current_language:
                end_call_msg = "Thank you so much for calling Everest Fleet. Wish you good day ahead"
            else:
                end_call_msg = "Everest Fleet को call करने के लिए बहुत-बहुत धन्यवाद"
            await self.session.say(text=end_call_msg)
        await hangup()
        return "Noted"

class IntakeUserInfoAgent(Agent):
    def __init__(self, chat_ctx, customer_name, contact_number, participant, call_state):
        logger.info("In IntakeUserInfoAgent")
        self.customer_name = customer_name
        self.contact_number = contact_number
        self.participant = participant
        self.contact_number_in_words = convert_number_to_conversational(self.contact_number)
        _prompt = intake_prompt
        _prompt = _prompt.replace("{{phone}}", self.contact_number)
        _prompt = _prompt.replace("{{current_time}}", datetime.now().strftime("%Y-%m-%d %H:%M"))
        # logger.info(f"Greeter Prompt: \n{_prompt}")
        # logger.info("-"*30)
        self._seen_results = set()
        self.call_state = call_state
        self.llm_obj = LLMPromptRunner(api_key=config_manager.get_openai_api_key())
        self.IntakeCustomerAppointmentLocationAgentGate = OneTimeGate()
        
        super().__init__(
            instructions=_prompt, chat_ctx=chat_ctx
        )

    async def on_enter(self):
        logger.info("In IntakeUserInfoAgent.on_enter()")
        await self.session.say(text=f"जी बहोत अच्छा, मैं आपकी details ले लेती हूँ. kya आपके पास valid driving license है?")

    async def _handoff_if_done(self, context: RunContext[UserData]):
        logger.info("In IntakeUserInfoAgent._handoff_if_done()")
        logger.info(context.userdata.summarize())

        if context.userdata.have_driving_license and context.userdata.is_valid_city:
            logger.info("In IntakeUserInfoAgent._handoff_if_done() 504")
            if self.IntakeCustomerAppointmentLocationAgentGate.acquire_once():
                logger.info("In IntakeUserInfoAgent acquired lock......................#######")

                logger.info("Passing the ball from Intake to Appointment Agent")
                self.session.update_agent(
                    IntakeCustomerAppointmentLocationAgent(
                            chat_ctx=self.session._chat_ctx,
                            customer_name=self.customer_name,
                            contact_number=self.contact_number,
                            city=context.userdata.city,
                            participant=self.participant,
                            call_state=self.call_state
                    )
                )
        elif not context.userdata.have_driving_license:
            logger.info("In IntakeUserInfoAgent._handoff_if_done() 516")
            await self.session.say("User must have valid driving license to proceed. Politely inform user that they can get valid driving license easily and once they have it, they can contact Everest fleet.")
            await self.end_call(instructions="Tell the customer that if they refer someone to earkart, they will get commision as well. Thank them for their time. Generate response in Hinglish.")
        else:
            logger.info("In IntakeUserInfoAgent._handoff_if_done() 520")
            return "noted"
        # if context.userdata.have_driving_license is None:
        #     logger.info("In IntakeUserInfoAgent._handoff_if_done() 530")
        #     logger.info(f"In IntakeUserInfoAgent._handoff_if_done() - have_driving_license None")
        #     return "politely ask customer to confirm if they have valid driving license. Ask in Hinglish language."
        # elif not context.userdata.have_driving_license:
        #     # hungup the call
        #     logger.info("In IntakeUserInfoAgent._handoff_if_done() 535")
        #     await self.session.say("User must have valid driving license to proceed. Politely inform user that they can get valid driving license easily and once they have it, they can contact Everest fleet.")
        #     await self.end_call(instructions="Tell the customer that if they refer someone to earkart, they will get commision as well. Thank them for their time. Generate response in Hinglish.")
        # elif context.userdata.city == 'NOT_GIVEN':
        #     logger.info(f"In IntakeUserInfoAgent._handoff_if_done() city: {context.userdata.city}  539")
        #     return "noted"
        # elif await self._is_valid_city(context=context):
        #     logger.info("In IntakeUserInfoAgent._handoff_if_done() 542")
        #     self.session.update_agent(
        #         AppointmentSchedulerAgent(
        #                 chat_ctx=self.session._chat_ctx,
        #                 customer_name=self.customer_name,
        #                 contact_number=self.contact_number,
        #                 participant=self.participant,
        #                 call_state=self.call_state
        #         )
        #     )
        # else:
        #     logger.info("In IntakeUserInfoAgent._handoff_if_done() 556")
        #     return "stored"
        # return "stored"

    @function_tool
    async def valid_driving_license(self, context: RunContext[UserData], have_driving_license: str):
        """Store if customer is interested in renting car for driving purpose and driving for Uber.

        have_driving_license: whether customer have valid driving license to drive car or not, strictly in Yes/No.
        """
        self.session.say(text="Hmm...")
        logger.info(f"In IntakeUserInfoAgent.valid_driving_license() {have_driving_license}")
        context.userdata.have_driving_license = have_driving_license
        if have_driving_license == "No":
            # hung the call stating reason
            return "Tell customer that valid driving license is must."
        return await self._handoff_if_done(context=context)

    @function_tool
    async def _driven_uber_before(self, context: RunContext[UserData], driven_uber_before: str):
        """
        Store whether customer has driven the uber before.
        driven_uber_before: whether customer has driven the Uber car before or not. strictly in Yes/No.
        """
        self.session.say(text="Hmm...")
        logger.info(f"In IntakeUserInfoAgent._driven_uber_before() driven_uber_before: {driven_uber_before}")
        context.userdata.driven_uber_before = driven_uber_before
        return await self._handoff_if_done(context=context)

    @function_tool
    async def is_uber_id_active(self, context: RunContext[UserData], is_active: str):
        """
        Store uber if of customer if he has already driven Uber before.

        is_active: Is customer uber id active? strictly in Yes/No.
        """
        logger.info(f"In IntakeUserInfoAgent.is_uber_id_active() is_active: {is_active}")
        context.userdata.is_user_id_active = is_active
        return await self._handoff_if_done(context=context)

    @function_tool
    async def city_interested(self, context: RunContext[UserData], city: str):
        """
        Store which city customer is interested in driving the car.

        city: city name where customer wants to drive the car.
        """
        def _is_valid_city(context: RunContext[UserData]) -> bool:
            """Check if city string contains any valid city name (English or Hindi).
            Returns True if found else False
            """
            city=context.userdata.city
            logger.info(f"In IntakeUserInfoAgent._is_valid_city() {city}, type: {type(city)}")
            if (city is None) or (not city):
                logger.info(f"I am here...")
                return False

            # mapping of possible spellings → normalized city
            city_aliases = {
                # Mumbai
                "mumbai": "Mumbai", "मुंबई": "Mumbai",
                
                # Delhi / NCR
                "delhi": "Delhi", "दिल्ली": "Delhi",
                "ncr": "NCR", "एनसीआर": "NCR",
                
                # Kolkata
                "kolkata": "Kolkata", "calcutta": "Kolkata",
                "kalkatta": "Kolkata", "कोलकाता": "Kolkata", "कलकत्ता": "Kolkata",
                
                # Bangalore
                "bangalore": "Bangalore", "bengaluru": "Bangalore",
                "बैंगलोर": "Bangalore", "बेंगलुरु": "Bangalore",
                
                # Hyderabad
                "hyderabad": "Hyderabad", "हैदराबाद": "Hyderabad",
                
                # Pune
                "pune": "Pune", "puna": "Pune", "पुणे": "Pune",
                
                # Chennai
                "chennai": "Chennai", "madras": "Chennai", "चेन्नई": "Chennai"
            }

            city_lower = city.lower()

            for alias, normalized in city_aliases.items():
                if alias.lower() in city_lower:
                    context.userdata.city = normalized
                    return True
            return False
        self.session.say(text="Hmm...")        
        logger.info(f"In IntakeUserInfoAgent.city_interested() city: {city}")
        context.userdata.city = city
        context.userdata.is_valid_city = _is_valid_city(context)
        return await self._handoff_if_done(context=context)

    # @function_tool
    # async def end_call(self, current_language: str, instructions: str = None):
    #     """
    #     This method hungup/cut/end the ongoing call. Call this method when user request to cut the call or you want to exit the call.
        
    #     current_language: strictly either "Hindi" Or "English"
    #     """
    #     # # Wait for current speech to finish
    #     # current_speech = ctx.session.current_speech
    #     # if current_speech:
    #     #     await current_speech.wait_for_playout()
    #     logger.info("In IntakeUserInfoAgent.end_call()")
    #     if instructions:
    #         self.session.generate_reply(instructions=instructions)
    #     else:
    #         if  "English" == current_language:
    #             end_call_msg = "Thank you so much for calling Everest Fleet. Wish you good day ahead"
    #         else:
    #             end_call_msg = "Everest Fleet को call करने के लिए बहुत-बहुत धन्यवाद"
    #         await self.session.say(text=end_call_msg)
    #     await hangup()
    #     return "Noted"

class IntakeCustomerAppointmentLocationAgent(Agent):
    def __init__(self, chat_ctx, participant, customer_name, contact_number, city, call_state):
        logger.info("In IntakeCustomerAppointmentLocationAgent")
        self.customer_name = customer_name
        self.contact_number = contact_number
        self.participant = participant
        self.contact_number_in_words = convert_number_to_conversational(self.contact_number)
        _prompt = appointment_prompt
        _prompt = _prompt.replace("{{phone}}", self.contact_number)
        _prompt = _prompt.replace("{{current_time}}", datetime.now().strftime("%Y-%m-%d %H:%M"))
        _prompt = _prompt.replace("{{city_interested}}", city)
        logger.info(f"IntakeCustomerAppointmentLocationAgent Prompt: \n{_prompt}")
        logger.info("-"*30)
        self._seen_results = set()
        self.call_state = call_state
        self.llm_obj = LLMPromptRunner(api_key=config_manager.get_openai_api_key())
        self.AppointmentSchedulerAgentGate = OneTimeGate()
        super().__init__(
            instructions=_prompt, chat_ctx=chat_ctx
        )
       
    async def on_enter(self):
        logger.info("In IntakeCustomerAppointmentLocationAgent.on_enter()")
        await self.session.say(text=f"जी बहोत अच्छा, मैं आपकी onboarding team के साथ appointment बुक कर देती हूँ? आप {self.session.userdata.city} शहर में किस लोकेशन में रहते हैं ")

    async def _handoff_if_done(self, context: RunContext[UserData]):
        if context.userdata.customer_location and context.userdata.customer_preferred_day:
            if await self.AppointmentSchedulerAgentGate.acquire_once():
                logger.info("In IntakeCustomerAppointmentLocationAgent: accquired LOCK$$$$$$$$$$$$$$$$$$$$")
                return self.session.update_agent(
                            AppointmentSchedulerAgent(
                                    chat_ctx=self.session._chat_ctx,
                                    customer_name=self.customer_name,
                                    contact_number=self.contact_number,
                                    participant=self.participant,
                                    call_state=self.call_state
                            )
                )
        return "noted"

    @function_tool
    async def customer_location_in_preferred_city(self, context: RunContext[UserData], location: str):
        """
        store customer current location.
        location: current location address of customer. 
        """
        context.userdata.customer_location = location
        await self._handoff_if_done(context=context)

    @function_tool
    async def customer_preferred_day(self, context: RunContext[UserData], day: str):
        """
        Which day customer is interested to book slot. strictly tomorrow/day-after-tommorow
        day: strictly tomorrow/day-after-tomorrow
        """
        context.userdata.customer_preferred_day = day
        await self._handoff_if_done(context=context)

class AppointmentSchedulerAgent(Agent):
    def __init__(self, chat_ctx, participant, customer_name, contact_number, call_state):
        logger.info("In AppointmentSchedulerAgent")
        self.customer_name = customer_name
        self.contact_number = contact_number
        self.participant = participant
        self.contact_number_in_words = convert_number_to_conversational(self.contact_number)
        _prompt = appointment_prompt
        _prompt = _prompt.replace("{{phone}}", self.contact_number)
        _prompt = _prompt.replace("{{current_time}}", datetime.now().strftime("%Y-%m-%d %H:%M"))
        logger.info(f"AppointmentSchedulerAgent Prompt: \n{_prompt}")
        logger.info("-"*30)
        self._seen_results = set()
        self.call_state = call_state
        self.llm_obj = LLMPromptRunner(api_key=config_manager.get_openai_api_key())
        self.ReferralBonusAgentGate = OneTimeGate()
        super().__init__(
            instructions=_prompt, chat_ctx=chat_ctx
        )
       
    async def on_enter(self):
        logger.info("In AppointmentSchedulerAgent.on_enter()")
        await self._book_an_appointment()

    @function_tool
    async def _book_an_appointment(self):
        await self.session.generate_reply(instructions="Politely ask user to wait for few seconds while you are booking the appointment. Genrate response in Hinglish.")
        await asyncio.sleep(0.5)

        contact_number = self.session.userdata.contact_number
        location = self.session.userdata.customer_location
        if contact_number and location:
            if await self.ReferralBonusAgentGate.acquire_once():
                logger.info("In AppointmentSchedulerAgent acquired lock......................#######")
                handle = self.session.userdata.bg_player.play(
                "background_mp3/short1.mp3",
                loop=True)
                await book_an_appointment(contact_number=contact_number, location=location)
                handle.stop()
                await asyncio.sleep(0.5)
                self.session.say("जी सर, लाइन पे बने रहने के लिए धन्यवाद")
                self.session.update_agent(ReferralBonusAgent(
                                chat_ctx=self.session._chat_ctx,
                                customer_name=self.customer_name,
                                contact_number=self.contact_number,
                                participant=self.participant,
                                call_state=self.call_state
                ))

class ReferralBonusAgent(Agent):
    def __init__(self, chat_ctx, participant, customer_name, contact_number, call_state):
        logger.info("In ReferralBonusAgent")
        self.customer_name = customer_name
        self.contact_number = contact_number
        self.participant = participant
        self.contact_number_in_words = convert_number_to_conversational(self.contact_number)
        _prompt = referral_agent_prompt
        _prompt = _prompt.replace("{{phone}}", self.contact_number)
        _prompt = _prompt.replace("{{current_time}}", datetime.now().strftime("%Y-%m-%d %H:%M"))
        logger.info(f"ReferralBonusAgent Prompt: \n{_prompt}")
        logger.info("-"*30)
        self._seen_results = set()
        self.call_state = call_state
        self.llm_obj = LLMPromptRunner(api_key=config_manager.get_openai_api_key())
        self.EndCallAgentGate = OneTimeGate()
        super().__init__(
            instructions=_prompt, chat_ctx=chat_ctx
        )
       
    async def on_enter(self):
        logger.info("In ReferralBonusAgent.on_enter()")
        await self.session.say(text=f"आपकी appoinement बुक कर दी गयी है, क्या मैं आपकी कोई और मदद कर सकती हूँ?")

    @function_tool
    async def _is_referral_done(self, context: RunContext[UserData], referral_done: str):
        """
        Stores if referral pitch is concluded or not. strictly in Yes/No.

        referral_done: strictly in Yes/No.
        """
        logger.info(f"In ReferralBonusAgent._is_referral_done() {referral_done}")
        if referral_done == "Yes":
            if await self.EndCallAgentGate.acquire_once():
                logger.info("In ReferralBonusAgent: accquired LOCK$$$$$$$$$$$$$$$$$$$$")
                self.session.update_agent(
                    EndCallAgent(
                            chat_ctx=self.session._chat_ctx,
                            customer_name=self.customer_name,
                            contact_number=self.contact_number,
                            participant=self.participant,
                            call_state=self.call_state                    
                    )
                )
        else:
            return "Please remind customer for referral program of Everest Fleet. Generate reponse in Hinglish."

class EndCallAgent(Agent):
    def __init__(self, chat_ctx, participant, customer_name, contact_number, call_state):
        logger.info("In EndCallAgent")
        self.customer_name = customer_name
        self.contact_number = contact_number
        self.participant = participant
        self.contact_number_in_words = convert_number_to_conversational(self.contact_number)
        _prompt = ""
        _prompt = _prompt.replace("{{phone}}", self.contact_number)
        _prompt = _prompt.replace("{{current_time}}", datetime.now().strftime("%Y-%m-%d %H:%M"))
        logger.info(f"EndCallAgent Prompt: \n{_prompt}")
        logger.info("-"*30)
        self._seen_results = set()
        self.call_state = call_state
        self.llm_obj = LLMPromptRunner(api_key=config_manager.get_openai_api_key())
        super().__init__(
            instructions=_prompt, chat_ctx=chat_ctx
        )
       
    async def on_enter(self):
        logger.info("In EndCallAgent.on_enter()")
        await self.session.say(text=f"जी, आपका समय देने के लिए धन्यवाद, आपका दिन शुभ हो")
        await self.end_call()

    async def end_call(self):
        """
        This method hungup/cut/end the ongoing call. Call this method when user request to cut the call or you want to exit the call.
        
        current_language: strictly either "Hindi" Or "English"
        """
        await hangup()
        return "Noted"


def create_agent(dial_info: dict[str, Any], call_state: CallState) -> GreeterAgent:
    """Factory function to create a MysyaraAgent instance"""
    return GreeterAgent(
        customer_name=dial_info["name"],
        contact_number=dial_info['phone'],
        call_state=call_state,
    )
