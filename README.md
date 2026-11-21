# Instagram auto-publish (free): Meta API + GitHub Actions

Ye bot har 30 minute mein dekhta hai ki kaunsi reel ka time aa gaya, aur use Instagram par **apne aap** daal deta hai
(caption, cover, AI label, pehla comment). Kharcha Rs 0. Laptop band ho tab bhi chalta hai.

## Ek baar ki setup (1 se 1.5 ghanta)

### 1. GitHub par naya PUBLIC repo
1. GitHub → **New repository** → naam `reel-queue` → **Public** → Create.
2. Mujhe repo ka naam bata do (`modhshubham3/reel-queue`). Main isme bot aur videos daal dungi.
3. Phir us repo mein ye 3 settings:
   - **Settings → Pages** → Source: *Deploy from a branch* → branch `ccr-cb619668-8pcm8x`, folder `/ (root)` → Save.
   - **Settings → Branches** → Default branch ko `ccr-cb619668-8pcm8x` karo (cron isi se chalta hai).
   - **Settings → Actions → General → Workflow permissions** → *Read and write permissions* → Save.

### 2. Meta (Facebook) developer app  [Meta ke official guide se]
1. `developers.facebook.com/apps` → **Create App**. Use case: **Other**. App type: **Business**. Naam aur email do.
2. App dashboard mein **Instagram** product → **Set up** → **API setup with Instagram login**.
3. **Add account** → apna Instagram account (professional aur **public** hona chahiye) → login.
4. **Generate token** → token copy karo (60 din chalta hai). Teeno accounts ke liye ye teen baar karo
   (`kahaniyon.wali.raat`, `interview.chai`, `bawaalmoments`). Har token alag jagah (Notepad mein) naam ke saath likh lo.
   Agar Instagram "tester invite" maange: Instagram app → Settings → Apps and websites → Tester invites → Accept. [Likely, verify nahi]

### 3. Tokens GitHub mein secret ki tarah
Repo → **Settings → Secrets and variables → Actions → New repository secret**:
`IG_TOKEN_KAHANI`, `IG_TOKEN_INTERVIEW`, `IG_TOKEN_GTA` (value = wahi token). Token kisi ko mat bhejna.

### 4. Pehla test
Repo → **Actions → publish-reels → Run workflow** → `only` = `i1`, `dry_run` = **ON** → Run (kuch post nahi hoga, sirf dikhayega).
Theek ho to dobara, is baar `dry_run` **OFF**: **i1 abhi Instagram par post ho jayega** (interview.chai). Dekho: video, cover, caption, AI label.

## Roz ka kaam
Kuch nahi. Naye hafte ki videos aur `queue.json` main push kar deti hoon.

## Har ~55 din mein
Token 60 din mein expire hota hai: Meta dashboard → **Generate token** dobara → GitHub secret update.

## Jo verify NAHI hua
- GitHub Pages ke link se Instagram video fetch kar leta hai ya nahi (pehla test batayega).
- Pehla comment API se jayega ya nahi (permission `instagram_business_manage_comments` token mein ho tab).
- Pehla comment **pin** nahi hota (API se pin nahi hota). Haath se pin karna padega.
- GitHub ka cron kabhi 5-15 minute late chalta hai.
