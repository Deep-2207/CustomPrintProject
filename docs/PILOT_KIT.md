# Pilot kit: your first 3 to 5 sellers in Ahmedabad

Everything here is a starting draft. Prices, wording and the agreement are **suggestions to adapt**, not facts about your market.
Have a native Gujarati speaker read the Gujarati text, and have an accountant or lawyer read the agreement, before you send them.

## 1. What the pilot must prove (30 days)

| Question | Proof you want | Where to see it |
| --- | --- | --- |
| Do sellers actually use it? | At least 3 shops each get 10 or more customer designs | Owner page, **Plans and invoices**, Designs column; seller's **Usage** page |
| Does it save them time or win orders? | The seller says so in their own words in the day-14 and day-30 calls | Your notes |
| Would they pay? | At least 2 of 3 say yes to the Starter price at the end | Day-30 call (script below) |
| What breaks? | A list of problems, each fixed or consciously parked | Your notes, then `STATUS.md` |

Decision at day 30: **go** if the three proofs above hold; **fix first** if sellers like it but a blocker repeats (for example "my 3D model does not work");
**stop or change the target** if nobody uses it after you personally helped them set up.

## 2. Who to approach

Start with shops that **already print on mugs, wristbands, bottles or T-shirts** and talk to customers on WhatsApp all day.
Ways to find them: search "mug printing Ahmedabad", "gift shop Ahmedabad" and "custom wristband" on Google Maps and Instagram; trade listings; your own network;
event merchandise and wedding-gift sellers. Visit in person with the demo on your phone: it sells itself in 60 seconds
(`docs/DEMO_SCRIPT.md`). Aim to talk to 15 to 20 shops to get 3 to 5 yes answers.

Best first yes: an owner who answers the phone, has repeat customers who send text by WhatsApp, and is annoyed by typing mistakes and "send me a preview".

## 3. The offer

| | Pilot (30 days) | After the pilot |
| --- | --- | --- |
| Monthly fee | Free (plan "Pilot", 100 designs) | Starter ₹999 (300 designs), Growth ₹2,499 (1,500 designs) *(placeholders: set in `app/config.py`)* |
| Extra designs | Not charged | ₹3 each on Starter, ₹2 on Growth |
| Setup | We do it for you: their products, colours, fonts, print areas | Optional one-time fee (for example ₹3,000), recorded per shop on the owner page |
| GST | Added to paid invoices (18%, `GST_PERCENT`) | |

The pitch in one line: **"Your customer types their message, sees it on the mug in 3D, and you get a print-ready file. No more preview screenshots by WhatsApp."**

## 4. Onboarding checklist (about 1 hour of your time per shop)

**Day 0, before the meeting**
- [ ] Ask for 2 photos of their best-selling product and the real printable size in mm (width and height of the print area).
- [ ] Ask whether they have a 3D model (`.glb`). If not, use the ready-made mug or wristband.

**Day 1, setup (do it for them)**
1. Create their shop: `python -m app.manage pilot-shop "Their Shop" their@email.com` (on the server: `docker compose exec app python -m app.manage ...`). It prints the login once.
2. Log in as them, **Products**: open each copied product, set their colours and fonts, set the print area's **real width and height in mm**, **Publish**.
3. Open the share link `/s/<shop>/<product>` on your phone. Type a real customer name. Check it looks right.
4. Send them the link and their login on WhatsApp (message below). Ask them to change the password under **Account**.
5. If they have a website: **Embed on your site**, add the website, send the snippet to their web person (`docs/EMBED_AND_API.md`).

**Day 3, check:** "Did you send the link to any customer yet?" Help them send the first one.

**Day 7, call (10 minutes)**
- How many customers used the link? (Check **Designs**.)
- Did anything confuse them or their customers?
- Did a design come out wrong when printed? (Open **Print files**, compare with what they printed.)

**Day 14, call:** same questions, plus "How many hours a week does this save?" and "What is the one thing you would change?"

**Day 30, decision call**
- Show their **Usage** page: designs saved, views.
- Ask: "If this cost ₹999 a month, would you keep it?" Then **be quiet and wait**. Write down the exact words.
- If yes: set their plan on the owner page (**Plans and invoices**) and send the first invoice CSV row.
- If no: ask "What price, or what missing thing, would change that?" Their answer is the most useful result of the whole pilot.

## 5. Messages you can copy

**First message (WhatsApp, English)**
> Hi {name}, this is {you} from {brand}. I built a tool that lets your customers type their name or message and see it on your mug / wristband in 3D, then you get a print-ready file. It takes the preview-by-WhatsApp work away. I'd like to set it up for {shop} free for 30 days, and I'll do all the setup. Can I show you in 5 minutes? Here's a 60-second demo: {demo link}

**First message (Gujarati, please have it checked)**
> નમસ્તે {name}, હું {you} {brand} તરફથી. મેં એક ટૂલ બનાવ્યું છે જેમાં તમારા ગ્રાહક પોતાનું નામ કે મેસેજ લખીને મગ / રિસ્ટબેન્ડ પર 3D માં જોઈ શકે છે, અને તમને પ્રિન્ટ માટે તૈયાર ફાઇલ મળે છે. WhatsApp પર પ્રિવ્યુ મોકલવાની મહેનત બચે છે. {shop} માટે 30 દિવસ મફત સેટઅપ કરી આપું, બધું હું જ કરીશ. 5 મિનિટ બતાવી શકું? 60 સેકન્ડનો ડેમો: {demo link}

**After setup**
> Your page is ready: {link}. Send this link to your customers instead of asking for the text. Login for your dashboard: {dashboard link}, email {email}, password {password} (please change it under Account). When a customer saves a design you'll see it under Designs, with a print file. I'll check in on Thursday.

**Day-30 follow-up**
> Hi {name}, your 30 days are up. In this time your customers made {n} designs. Would you like to continue? Starter is ₹999 a month (300 designs included). I'm happy to keep your setup as it is.

## 6. Pilot agreement (one page, plain language: have it reviewed)

> **Pilot between {Your business} ("we") and {Shop} ("the seller")**
> 1. **What we provide:** use of the customizer for the seller's products for 30 days from {date}, setup help by email, phone and WhatsApp, at no charge.
> 2. **What the seller agrees to:** share the link with real customers, give honest feedback in two short calls, and tell us if something goes wrong.
> 3. **Customer designs and files** belong to the seller and their customers. We keep them only to run the service, do not sell them, and delete them within 30 days of a written request.
> 4. **After the pilot:** nothing is charged unless the seller agrees in writing to a paid plan. If they do not continue, we turn the shop off and give them a copy of their designs on request.
> 5. **No promises:** during the pilot the service is provided as it is. We aim for it to be available every day but may restart it for fixes. We are not responsible for prints made from a file the seller did not check.
> 6. **Either side can stop at any time** by telling the other.
>
> Signed: ____________ (we)   ____________ (seller)   Date: ________

## 7. Questions for the feedback form (5 minutes, Google Forms is fine)

1. How many of your customers used the link? (none / a few / most)
2. What did they like? What confused them?
3. Did you print any design from our files? Did anything come out wrong? What?
4. Which products or print areas do you want added?
5. How much time per week did this save you? (none / 1 hour / 3 hours / more)
6. Would you keep using it at ₹999 a month? Why or why not?
7. Would you recommend it to another seller? Who?

## 8. What to do when…

| Situation | Action |
| --- | --- |
| A seller forgot the password | `python -m app.manage reset-password their@email.com`, then tell them the new one on a call |
| A customer's text does not fit | The text shrinks to fit the area; the seller can widen the print area or raise "Max letters" in the product editor |
| The seller wants a new product shape | Ask for a `.glb` (see the README for the rules); if they have none, note the shape: it tells you which template to build next |
| The print came out different from the preview | Ask for the design id, open **Print files**, compare the PNG with the printed item, and check the real size (mm) of the print area |
| The site is down | `docker compose ps` and `docker compose logs app` on the server (`docs/DEPLOY.md`) |
| A seller asks for a discount | Offer a longer free pilot or a lower setup fee before cutting the monthly price; record what they said |
