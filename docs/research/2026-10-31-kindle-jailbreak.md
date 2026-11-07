# Kindle jailbreak (current methods, OTA blocking, KOReader for BiteSIze): research note

**Date:** 31 October 2026  
**Scope:** Personal project. The user owns a **Kindle Paperwhite 11th gen (PW5, 2021) on firmware 5.19.1** and wants to jailbreak it to unlock features beyond the stock reader. BiteSIze emails a daily EPUB digest to the Kindle today (see [2026-08-14-kindle-interactive-epub.md](2026-08-14-kindle-interactive-epub.md) for stock-Kindle limits and [2026-08-30-kindle-auto-delete.md](2026-08-30-kindle-auto-delete.md) for the cloud-clutter problem).  
**Method:** Community-canonical sources first. The KindleModding wiki and the **data files its Jailbreak Wizard actually runs on** (`jailbreaks.json`, `models.json`, `jailbreakFinder.js`), plus each method's page source on GitHub. Then KOReader source code and wiki, MobileRead, Amazon help pages, and dated news for firmware rollouts. Uncertain facts are marked as such. This note links to the canonical guides and does not restate exploit steps.

**How to read this:** Jailbreak support is a moving target. Amazon is rolling out new firmware **right now** (5.20.2, reported 30–31 Oct 2026). Every version range below comes from the wizard's data as fetched on 31 Oct 2026. Re-run the [Jailbreak Wizard](https://kindlemodding.org/jailbreak-wizard.html) before you start; it overrides this note.

---

## Your device: PW5 on 5.19.1

**Verdict: jailbreakable today.** The wizard's rules match three methods for PW5 at 5.19.1. The wizard lists them in this order, and the first one is its recommendation:

| Order | Method | PW5 firmware range (wizard data) | Needs | Notes |
|---|---|---|---|---|
| **1 (recommended)** | [SpiderCat](https://kindlemodding.org/jailbreaking/SpiderCat/) | 5.16.3 – 5.19.5 | Wi-Fi, no PC required | Released 1 Sep 2026. You open a book, sideloaded over USB or downloaded in the Kindle browser. |
| 2 | [Véra](https://kindlemodding.org/jailbreaking/Vera/) | 5.17.1 – 5.20.1.0.2 | Wi-Fi, Kindle browser | Released 10 Aug 2026. You download two books in the browser and set font/theme values. Its page says it covers "all firmwares up to 5.20.1" on KT5, PW5, KT6, PW6, CS, KS, KS2. |
| 3 | [SpringBreak](https://kindlemodding.org/jailbreaking/SpringBreak/) | 5.18.1 – 5.19.2.0.1 | PC + USB, Kindle **registered** to Amazon | Released 22 Jun 2026. The wizard drops it if the device can't be registered. |

Sources: [`jailbreaks.json`](https://kindlemodding.org/jailbreaks.json) (last commit "Shadow/Add Shadow to jailbreaks.json", 25 Oct 2026, per the [repo history](https://github.com/KindleModding/kindlemodding.github.io/commits/main/static/jailbreaks.json)) and the matching logic in [`jailbreakFinder.js`](https://kindlemodding.org/jailbreakFinder.js). I re-ran that logic offline for PW5:

| If your PW5 ends up on… | Methods the wizard returns |
|---|---|
| 5.19.1 (now) or 5.19.2 | SpiderCat, Véra, SpringBreak (SpringBreak only if the device can register) |
| 5.19.6 – 5.20.1.x | Véra only |
| **5.20.2** (rolling out now) | **None** |

**What to avoid:**

- **Letting it update.** [Notebookcheck (31 Oct 2026)](https://www.notebookcheck.net/Kindle-s-latest-software-update-introduces-useful-feature.1438412.0.html) says 5.20.2 is rolling out automatically, is about 643 MB, and has no published device list yet. Whether PW5 gets it is **unknown**. 5.20.2 is above every range in the wizard data. Keep Airplane Mode on and fill storage before you go online again (section 3).
- **Methods outside your range.** WinterBreak stops at 5.18.0.2, Sanctuary at 5.18.3, AdBreak at 5.18.5.0.1, and Nosebleed at 5.18.6 for PW5. Shadow does not list PW5, and LanguageBreak stops at 5.16.2.1.1 ([LanguageBreak](https://kindlemodding.org/jailbreaking/Legacy/LanguageBreak.html)).
- **The per-model table on the wiki.** The `jailbreak` column in [`models.json`](https://kindlemodding.org/models.json) still lists only Sanctuary / WinterBreak2 / WinterBreak / SpringBreak / AdBreak for PW5, and neither SpiderCat nor Véra. It lags `jailbreaks.json`, which is what the wizard actually uses.
- **Factory reset.** KindleModding says not to do one "without an experienced person's advice" ([Jailbreaking lander](https://kindlemodding.org/jailbreaking/)).

**Downgrade?** You don't need one: 5.19.1 is covered. For the record, downgrading **requires an existing jailbreak** and can't go below the firmware the device shipped with. KindleModding also warns that "some models might not be able to downgrade below 5.18.x" because of bootloader hardening ([Downgrading](https://kindlemodding.org/firmware-and-flashing/downgrading/)). PW5 shipped on 5.14.0 ([`models.json`](https://kindlemodding.org/models.json)). If the device reaches 5.20.2 before you jailbreak, waiting for a new method is the only option. Downgrading isn't one.

---

## 1. Identify model and firmware

- **Firmware:** `⋮ (three dots) → Settings → Device options → Device info`. The version is the dotted number after "Kindle". Write down **every** segment (e.g. `5.19.1` vs `5.19.1.0.1`). The wizard compares all of them ([Véra step 2](https://kindlemodding.org/jailbreaking/Vera/), [Wizard](https://kindlemodding.org/jailbreak-wizard.html)).
- **Model:** the same Device info screen shows the model name on newer devices. Otherwise use the serial there, on the back of the device, or at amazon.com/mydevices ([Amazon: Identify Your Kindle E-Reader](https://www.amazon.com/gp/help/customer/display.html?nodeId=GK33S847NN4V6Y83)).
- **Serial prefix → model:** the wizard asks for the first 8 serial characters. Serials starting with `G` use **characters 4–6** as the device code. Older hex-style serials use characters 3–4 ([`jailbreakFinder.js`](https://kindlemodding.org/jailbreakFinder.js) `getSerialInfo`). The code → model map is [`models.json`](https://kindlemodding.org/models.json). PW5 codes: `1LG 1Q0 1PX 1VD 219 21A 2BH 2BJ 2DK`. Example: a serial starting `G0011PX…` has code `1PX`, which maps to PW5.
- **Registration and ads:** the wizard also asks whether the device can register with Amazon ("Amazon can blacklist them") and whether it shows lock-screen ads. AdBreak needs ads; WinterBreak and SpringBreak need registration ([Wizard](https://kindlemodding.org/jailbreak-wizard.html), [`jailbreaks.json`](https://kindlemodding.org/jailbreaks.json)).

---

## 2. Methods and ranges (all models, wizard data 31 Oct 2026)

Ranges are inclusive. "all listed" means the same range applies to every model in that method's list.

| Method | Released | Models | Firmware | Requires |
|---|---|---|---|---|
| [WinterBreak2](https://kindlemodding.org/jailbreaking/WinterBreak2/) | n/a | PW–PW5, KV, KT2–KT5, KOA–KOA3, KS | 5.6.1.1 – 5.16.3 (+5.16.5) | Experimental Browser |
| [SpiderCat](https://kindlemodding.org/jailbreaking/SpiderCat/) | 1 Sep 2026 | PW4, KT4, KOA3, PW5, KT5, KT6, PW6, CS, KS, KS2 | 5.16.3 – 5.19.5 | Wi-Fi |
| [Véra](https://kindlemodding.org/jailbreaking/Vera/) | 10 Aug 2026 | PW5, KT5, KT6, PW6, CS, KS, KS2 | 5.17.1 – 5.20.1.0.2 | Wi-Fi, browser |
| [Nosebleed](https://kindlemodding.org/jailbreaking/Nosebleed/) | 2 Mar 2026 | KT5, PW5, KOA3 / PW6, KT6 | 5.16.4 – 5.18.6 / 5.16.4 – 5.17.1.0.4 | PC, browser |
| [Sanctuary](https://kindlemodding.org/jailbreaking/Sanctuary/) | 30 Jun 2026 | PW4, KT4, KOA3, PW5, KT5, KS, KT6, PW6, KS2, CS | 5.16.4 – 5.18.3 (not 5.16.5) | Browser |
| [WinterBreak](https://kindlemodding.org/jailbreaking/WinterBreak/) | 1 Jan 2025 | PW through CS (18 models) | 5.6.1.1 – 5.18.0.2 | PC, registration |
| [SpringBreak](https://kindlemodding.org/jailbreaking/SpringBreak/) | 22 Jun 2026 | KT5, PW5 / KT4, PW4 | 5.18.1 – 5.19.2.0.1 / 5.18.1 – 5.18.1.1.1 | PC, registration |
| [Shadow](https://kindlemodding.org/jailbreaking/Shadow/) | 26 Oct 2026 | KS, KS2, CS, PW6, KT6 | 5.19.4 – 5.19.6 | PC (Linux/macOS; Windows "temporarily removed") |
| [AdBreak](https://kindlemodding.org/jailbreaking/AdBreak/) | 24 Sep 2025 | KOA3, PW5, KT5, KS, KT6, PW6 / PW4, KT4 | 5.18.1 – 5.18.5.0.1 / 5.18.1 only | PC, registration, ad-supported |
| [LanguageBreak](https://kindlemodding.org/jailbreaking/Legacy/LanguageBreak.html) (legacy) | n/a | per wizard | ≤ 5.16.2.1.1 | n/a |

**No public method** (per [`models.json`](https://kindlemodding.org/models.json), "None Available"): Kindle Scribe 3rd gen (KS3), Scribe Colorsoft (KSC), Kindle 2026 (KT7, ships on 5.20.0), Paperwhite 2026 (PW7, ships on 5.20.0.0.1). Véra's page says ports to KS3, KSC and KT7 are planned ([Véra](https://kindlemodding.org/jailbreaking/Vera/)).

**Firmware with no method today:** anything above 5.20.1.0.2, including **5.20.2**. KindleModding says jailbreaks are "commonly patched by Amazon" and a new one has to be waited for. It also says "you can never 'update' a jailbreak", because each method is a different route to the same result ([Jailbreaking lander](https://kindlemodding.org/jailbreaking/)).

**Firmware context (news, not Amazon):** [the-ebook-reader](https://blog.the-ebook-reader.com/2026/08/04/kindle-update-5-19-6-released-what-changes-does-it-contain/) reported in Aug 2026 that 5.19.6 went to "all current Kindles", while the "previous gen Kindle Paperwhite and basic Kindle are still on 5.19.2". Amazon's own [software updates page](https://www.amazon.com/gp/help/customer/display.html?nodeId=GKMQC26VQQMM8XSW) returned HTTP 503 when fetched, so **PW5's current official firmware was not verified**.

---

## 3. Blocking OTA updates

### Before jailbreaking

From [Prevent Automatic Updates](https://kindlemodding.org/jailbreaking/prevent-auto-update/):

- Updates can trigger when you open the Store, register, connect to Wi-Fi "even briefly", or reboot while online.
- **Turn on Airplane Mode first**, then **fill storage until only 50–90 MB is free**, so an update can't download.
- **PW5 is 11th gen and uses MTP**, so the `Filler.sh` script "will not work". Copy the matching pre-made filler files from [Crosunt223/Kindle-Filler-Disk/MTP](https://github.com/Crosunt223/Kindle-Filler-Disk/tree/main/MTP) (`fill_8gb.zip`, `fill_16gb.zip`, `fill_32gb.zip`, …) to the root manually. macOS has no built-in MTP client. [OpenMTP](https://openmtp.ganeshrvel.com/) lists the Kindle Paperwhite as compatible. That tool choice is mine, not KindleModding's.
- Delete any `update*.bin`, `update.partial.bin` or `update.bin.tmp.partial` in the storage root. If none exist, nothing has downloaded yet.
- Check Device info for 50–90 MB free before turning Wi-Fi on. SpiderCat and Véra **need Wi-Fi during the jailbreak**, which is why the storage fill matters.
- The legacy trick of creating a **folder** named `update.bin.tmp.partial` is documented only for **firmware ≤ 5.10.x** ([Disabling OTA Updates](https://kindlemodding.org/jailbreaking/Legacy/post-jailbreak/disable-ota.html)). It does not apply to 5.19.1.

### After jailbreaking

- **Modern methods block updates for you.** SpiderCat's and Véra's final step says "Updates have been automatically blocked for you". After that you remove `.bin` files and then delete the filler ([SpiderCat](https://kindlemodding.org/jailbreaking/SpiderCat/), [What's Next](https://kindlemodding.org/jailbreaking/whats-next/index.html)).
- **Jobman** (Jailbreaking Manager, firmware ≥ 5.16.3) has a toggle to block and unblock updates ([Jobman](https://kindlemodding.org/jailbreaking/whats-next/jailbreaking-manager/)). The `ota.sh` scriptlet re-enables OTA ([Unjailbreaking](https://kindlemodding.org/jailbreaking/faq/unjailbreaking.html)).
- **`renameotabin`** (KUAL extension, firmware 5.11+) is the **legacy** route. You need to run its "Restore" before any factory reset, downgrade or update ([Disabling OTA Updates](https://kindlemodding.org/jailbreaking/Legacy/post-jailbreak/disable-ota.html)). It isn't needed on the modern path.

---

## 4. Post-jailbreak essentials

| Tool | Status on the modern path (PW5 / 5.19.x) | Source |
|---|---|---|
| **KPM** (package manager) | Pre-installed by the modern jailbreak. Driven from the home search bar: `;kpm update`, `;kpm install <pkg>` | [What's Next](https://kindlemodding.org/jailbreaking/whats-next/index.html), [KPM](https://kindlemodding.org/kindle-dev/kpm/index.html) |
| **Scriptlets** | `.sh` files in `documents/` show up as books. This is how most homebrew ships | [Installing Homebrew](https://kindlemodding.org/jailbreaking/whats-next/installing-homebrew.html) |
| **Jobman** | OTA toggle, SSH over USB and Wi-Fi, battery health, optional (experimental) boot recovery | [Jobman](https://kindlemodding.org/jailbreaking/whats-next/jailbreaking-manager/) |
| **Hotfix** | Keeps a jailbreak alive across updates. The legacy page says to skip it for WinterBreak/SpringBreak/Sanctuary because it's already installed. For modern ("hdnext") jailbreaks, the unjailbreak FAQ says they "try to persist or recover the jailbreak after updates". **Not verified** whether SpiderCat/Véra bundle the same hotfix | [Hotfix](https://kindlemodding.org/jailbreaking/Legacy/post-jailbreak/setting-up-a-hotfix/), [Unjailbreaking](https://kindlemodding.org/jailbreaking/faq/unjailbreaking.html) |
| **KUAL / MRPI** | The current Homebrew guide calls KUAL "now obsolete" and says it doesn't work. KUAL/MRPI install now lives under *Legacy* | [Installing Homebrew](https://kindlemodding.org/jailbreaking/whats-next/installing-homebrew.html), [KUAL & MRPI](https://kindlemodding.org/jailbreaking/Legacy/post-jailbreak/installing-kual-mrpi/) |
| **KOReader** | `;kpm install koreader`, then `;kpm launch koreader`. Latest stable release is **v2026.07.1** (1 Aug 2026) | [Getting KOReader](https://kindlemodding.org/jailbreaking/whats-next/getting-koreader/), [KOReader releases](https://github.com/koreader/koreader/releases) |

NiLuJe's MobileRead snapshots (the classic source for KUAL/MRPI/USBNet) are not part of the modern KindleModding flow. I didn't verify their current state, and you don't need them for PW5 on 5.19.x.

### KOReader capabilities relevant to a news digest

- **Native EPUB, no Amazon conversion.** The stock path sends EPUB through Send to Kindle, which converts it ([earlier note §2](2026-08-14-kindle-interactive-epub.md)). KOReader opens the file as-is. Fonts and plugins: [KOReader user guide](https://koreader.rocks/user_guide/).
- **OPDS catalog sync.** You add a custom catalog (host, port, optional credentials). "Sync" downloads new items from catalogs sorted by newest into a required sync folder. There's a per-catalog cap ("default 50") and a file-type filter. Authentication must be **HTTP Basic, not Digest** ([OPDS wiki](https://github.com/koreader/koreader/wiki/OPDS-support)). The plugin registers a **"Sync all OPDS catalogs"** dispatcher action ([`opds.koplugin/main.lua`](https://github.com/koreader/koreader/blob/master/plugins/opds.koplugin/main.lua)).
- **Profiles auto-execute.** A profile can run dispatcher actions automatically **"on KOReader start"** or **"on wake-up"**, among other triggers ([`profiles.koplugin/main.lua`](https://github.com/koreader/koreader/blob/master/plugins/profiles.koplugin/main.lua)). Together with the OPDS action, this means a sync on wake-up.
- **News downloader (RSS/Atom → EPUB).** You configure feeds in `<koreader>/news/feed_config.lua` with `limit`, `download_full_article`, `include_images`, `enable_filter`/`filter_element`, `max_age = "7d"`, and form-login `credentials`. Each feed gets its own subfolder, and the menu has "Delete all downloaded items" ([`feed_config.lua`](https://github.com/koreader/koreader/blob/master/plugins/newsdownloader.koplugin/feed_config.lua), [`main.lua`](https://github.com/koreader/koreader/blob/master/plugins/newsdownloader.koplugin/main.lua), [wiki](https://github.com/koreader/koreader/wiki/News-downloader)). I found **no dispatcher action** for it in the source, so it can't be auto-run from a profile. Not confirmed otherwise.
- **Wallabag.** Downloads articles as individual EPUBs. Settings include `is_delete_finished`, `is_auto_delete` and `is_archiving_deleted`, so finished articles can be removed on device and archived on the server ([Wallabag wiki](https://github.com/koreader/koreader/wiki/Wallabag)).
- **SSH.** Dropbear server under Tools → Network → SSH server, user `root`, keys in `settings/SSH/authorized_keys`. The guide uses port 2222 ([SSH wiki](https://github.com/koreader/koreader/wiki/SSH)). Jobman also offers SSH ([Jobman](https://kindlemodding.org/jailbreaking/whats-next/jailbreaking-manager/)).
- **Scheduling on the device.** Classic cron is `/etc/crontab/root` (BusyBox crond), but it **doesn't run while the Kindle sleeps** ([MobileRead K3 thread](https://www.mobileread.com/forums/showthread.php?t=156472), [fnordig.de](https://fnordig.de/2015/05/14/using-a-kindle-for-status-information/)). **KindleCron / `kron`** uses powerd's `rtcWakeup` to wake the device for scheduled jobs. It was tested only on KT4 5.13.6 and PW4 5.17.1.0.3 ([MobileRead t=374083](https://www.mobileread.com/forums/showthread.php?t=374083), [GitHub](https://github.com/lennardollesch/KindleCron)). **Untested on PW5 / 5.19.x.**
- **Stock stays.** Jailbreaking "doesn't affect the stock Kindle interface" and doesn't slow the device ([Unjailbreaking](https://kindlemodding.org/jailbreaking/faq/unjailbreaking.html)). Send to Kindle keeps working alongside KOReader.

### Ideas for BiteSIze (not built, not tested)

1. **OPDS feed of digests.** BiteSIze publishes an OPDS Atom feed (newest first) listing recent `output/*.epub`. KOReader syncs it into a `BiteSIze/` folder, and a Profile runs "Sync all OPDS catalogs" **on wake-up**, so the morning digest arrives when you pick up the Kindle. This replaces email → Amazon conversion → cloud clutter. Grounding: OPDS sync and Basic auth ([OPDS wiki](https://github.com/koreader/koreader/wiki/OPDS-support)), dispatcher action and auto-execute (source links above). **Conflict:** CLAUDE.md says the dashboard binds `127.0.0.1` and must not be exposed. A Kindle on Wi-Fi can't reach that. You'd need either a separate read-only LAN listener or a static feed hosted elsewhere, behind HTTPS + Basic auth. That decision is the user's.
2. **Keep only the last N digests.** OPDS sync caps how many files it *downloads* per catalog. I found no evidence that it deletes old ones. Pruning options: a scriptlet you tap, or a `kron` job like `ls -t /mnt/us/BiteSIze/*.epub | tail -n +8 | xargs rm` (shell sketch, untested). The cron caveats above apply.
3. **Per-article mode through Wallabag.** BiteSIze posts selected articles to a Wallabag instance. KOReader pulls them, deletes them when finished, and archives them on the server. That gives read-state feedback BiteSIze could later read through the Wallabag API ([Wallabag wiki](https://github.com/koreader/koreader/wiki/Wallabag)).
4. **Push over SSH.** The Mac's launchd job `scp`s the EPUB to the Kindle. This only works while the Kindle is awake and on Wi-Fi ([SSH wiki](https://github.com/koreader/koreader/wiki/SSH)). Weaker than idea 1, which is a pull.
5. **News downloader as a fallback.** BiteSIze exposes a curated RSS feed and KOReader builds per-item EPUBs with `max_age` ([`feed_config.lua`](https://github.com/koreader/koreader/blob/master/plugins/newsdownloader.koplugin/feed_config.lua)). You lose BiteSIze's section covers and summaries layout. Sync is manual, since I found no dispatcher action.

---

## 5. Risks and recovery

| Risk | What the sources say |
|---|---|
| **Bricking** | WinterBreak's page notes beta testing "bricked some Kindles" ([WinterBreak](https://kindlemodding.org/jailbreaking/WinterBreak/)). Homebrew from unknown sources "can result in installing malware or bricking your device" ([Installing Homebrew](https://kindlemodding.org/jailbreaking/whats-next/installing-homebrew.html)). Downgrades across large jumps can white-screen the device ([Downgrading](https://kindlemodding.org/firmware-and-flashing/downgrading/)). |
| **Warranty** | Amazon's one-year limited warranty covers hardware "not subject to … alteration" ([Amazon warranty](https://www.amazon.com/gp/help/customer/display.html?nodeId=201014520)). It does not mention software jailbreaks specifically, so whether this voids the warranty is **unclear**. KindleModding names warranty repair as a reason to unjailbreak first ([Unjailbreaking](https://kindlemodding.org/jailbreaking/faq/unjailbreaking.html)). |
| **ToS** | Older Kindle license terms said users may not "modify, reverse engineer, decompile, or disassemble the Kindle or the Software" ([2010 Kindle User's Guide, App. B](https://kindle.s3.amazonaws.com/AppB_07072010_English.pdf)). The current [Kindle Store Terms of Use](https://www.amazon.com/gp/help/customer/display.html?nodeId=201014950) returned 503, so **the current wording was not verified**. |
| **Amazon account** | The wizard warns that Amazon can blacklist devices from registering, which breaks registration-based methods ([Wizard](https://kindlemodding.org/jailbreak-wizard.html)). I found no source documenting account bans for jailbreaking. |
| **Losing the jailbreak** | Updates can remove it, hence update blocking ([lander](https://kindlemodding.org/jailbreaking/)). A factory reset on a jailbroken, update-blocked device "prevents normal installation of official update files". Recovery is to reflash the matching `.bin` from FTVDB, then re-jailbreak ([Recovering From a Reset](https://kindlemodding.org/jailbreaking/faq/recovering-from-a-reset.html)). |
| **Recovery tools** | Jobman Recovery Mode (≥ 5.16.3, experimental): you tap during the boot window, create a `JOBMAN_RECOVERY` file, or it starts automatically after 3+ quick reboots. It can generate logs and offers USB SSH ([Kindle Recovery](https://kindlemodding.org/jailbreaking/faq/kindle-recovery.html)). You have to install it from Jobman first. |
| **Undo** | Re-enable OTA (`ota.sh` or Jobman), factory reset, then install a same-or-newer `.bin` ([Unjailbreaking](https://kindlemodding.org/jailbreaking/faq/unjailbreaking.html)). |

---

## 6. Checklist (PW5 on 5.19.1)

Follow the linked guide at every step. This list only puts them in order.

1. **Now:** Airplane Mode **on**. Don't open the Store, don't register, don't reboot while online.
2. Confirm the full firmware string and serial in Device info (section 1).
3. Back up `documents/` over MTP (OpenMTP on macOS). Optional, but recommended before anything risky.
4. Fill storage to 50–90 MB free with the **MTP filler files**. Delete any `update*.bin` / `.partial` in the root, then check free space in Device info ([Prevent Automatic Updates](https://kindlemodding.org/jailbreaking/prevent-auto-update/)).
5. Read the [Jailbreaking lander](https://kindlemodding.org/jailbreaking/) top to bottom (the wizard shows a warning until you do), then run the [Wizard](https://kindlemodding.org/jailbreak-wizard.html). Expect **SpiderCat**.
6. Wi-Fi on, then follow [SpiderCat](https://kindlemodding.org/jailbreaking/SpiderCat/). If it ends with `abort:no-firm` or fails, try [Véra](https://kindlemodding.org/jailbreaking/Vera/). If the device can register, [SpringBreak](https://kindlemodding.org/jailbreaking/SpringBreak/) is a third option.
7. After the reboot: delete `.bin` files, **then** the filler ([What's Next](https://kindlemodding.org/jailbreaking/whats-next/index.html)).
8. Run `;kpm update`, then open [Jobman](https://kindlemodding.org/jailbreaking/whats-next/jailbreaking-manager/). Confirm updates are blocked, and optionally install Recovery.
9. Run `;kpm install koreader` ([Getting KOReader](https://kindlemodding.org/jailbreaking/whats-next/getting-koreader/)).
10. Optional for BiteSIze: decide on the OPDS idea (section 4, idea 1) and its exposure question before building anything.

**If the device is already on 5.19.6 – 5.20.1.x:** only Véra applies. **If it's on 5.20.2 or later:** stop and wait for a new method, keeping it full and offline.

---

## Open questions / not verified

- Whether PW5 is in the 5.20.2 rollout. Amazon hasn't published release notes yet ([Notebookcheck](https://www.notebookcheck.net/Kindle-s-latest-software-update-introduces-useful-feature.1438412.0.html)).
- PW5's current official firmware on Amazon's updates page (503 when fetched).
- Whether SpiderCat/Véra install the same persistence hotfix as WinterBreak/SpringBreak/Sanctuary.
- KindleCron on PW5 / 5.19.x.
- The current Kindle Store Terms of Use wording on device modification.
