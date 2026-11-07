# Kindle and Apple Books digest backlog — bulk cleanup research note

**Date:** 31 October 2026  
**Scope:** Personal project. BiteSIze emails one EPUB per run to an approved `@kindle.com` address (`kindle.py` → `send_to_kindle`) and copies the same file into the iCloud Books folder (`books.py` → `copy_to_icloud_books`). After weeks of daily runs, the Kindle cloud library, the device, and Apple Books all hold a long tail of old digests. `output/` held 129 EPUBs on 31 October 2026 (91 `Resumo de Notícias - …`, 31 `News Digest - …`).  
**Method:** Amazon Customer Service pages first (fetched 31 October 2026), then the Amazon Kindle user guide, Apple Support, the Calibre manual, OpenMTP, MobileRead. Forum and blog claims are labelled **community** or **unverified**.  
**Builds on:** [2026-08-30-kindle-auto-delete.md](2026-08-30-kindle-auto-delete.md). That note covers the absence of an auto-delete API and why BiteSIze should not script Amazon's site. This note adds the bulk-delete mechanics for the device, USB/MTP on macOS, Brazil, Apple Books, and app-side changes tied to the current code.

**How to read this:** Bulk cleanup is a manual job on Amazon's website. The device is useful for freeing space, not for clearing the cloud library. Nothing from Amazon or Apple automates it. BiteSIze can only send fewer cloud copies and prune its own files.

---

## Recommended steps

1. **Cloud (does the most):** [amazon.com/mycd](https://www.amazon.com/mycd) (Brazil accounts: [amazon.com.br/mycd](https://www.amazon.com.br/mycd)) → **Content** → change the type filter from Books to **Docs** → tick digests (or **Select All** on the page) → **Delete** → confirm. Repeat page by page. Deleting here removes the item from the account and every device ([§1](#1-manage-your-content-and-devices-mycd)).
2. **Sync the Kindle** so deleted items leave the device ([Sync Your Kindle E-Reader](https://www.amazon.com/gp/help/customer/display.html?nodeId=GDCAMDFMC2LZP6BR)).
3. **Device leftovers:** **Settings → Device options → Storage management → Manual Removal → Docs** to remove many downloads at once ([§2](#2-on-the-kindle-e-reader)).
4. **Stop new cloud copies (optional, trade-off):** Preferences → Personal Document Settings → turn off **Personal Document Archiving** ([§4](#4-personal-document-archiving)).
5. **Apple Books:** remove old digests in Books on Mac or iPhone. Apple documents only one-at-a-time removal ([§6](#6-apple-books-icloud-copies)).
6. **Going forward:** keep BiteSIze's dated filenames (resending a fixed name does not replace the old copy, [§5](#5-automation-and-app-side-mitigations)). Add an opt-in local prune for `output/` and the iCloud Books folder.

---

## 1. Manage Your Content and Devices (mycd)

| Question | Answer | Source |
|---|---|---|
| Where are Send-to-Kindle EPUBs? | **Content** tab, filter **Docs** (Documents). They are not listed under Books. | Amazon forum (community), cited in [2026-08-30 note §2](2026-08-30-kindle-auto-delete.md#2-remote-deletion--website-apps-api); Amazon's own Kindle for Windows page also uses **View → Docs** in mycd ([Remove Personal Documents from Kindle for Windows](https://www.amazon.com/gp/help/customer/display.html?nodeId=TEYEjk3h6UBK0eAr0c)) |
| Multi-select? | Yes. Checkbox per row, **Select All**, then **Delete**. | **Community / unverified by Amazon help.** No Amazon help page reviewed documents the bulk Delete button. Steps from [Oficina da Net (pt-BR)](https://www.oficinadanet.com.br/amazon/36450-excluir-livros-biblioteca-kindle) and [Trusted Reviews](https://www.trustedreviews.com/how-to/how-to-remove-all-your-books-from-a-kindle-online-4289146) |
| How many at once? | **About 25 per page.** Select All covers the current page only. | **Community:** [Amazon UK forum thread](https://uk.amazonforum.com/s/question/0D56Q0000B8xSlSSQU/using-manage-your-content-and-devices-to-remove-bulk-items-reversibly). Not confirmed by Amazon. |
| Does Delete remove it from devices? | Yes. It removes the item from the cloud and from registered devices after sync. | Device-side equivalent in Amazon's words: **Permanently delete** removes items "from your cloud account and all your devices" ([Remove Books from Your Kindle E-Reader](https://www.amazon.com/gp/help/customer/display.html?nodeId=TIEM9w0fUmk2jXEknD)) |
| Remove from one device only, in bulk? | **Not reliable.** A forum report says "Deliver or Remove from Device" acts on one item even when many are ticked. | **Community:** [Amazon UK forum thread](https://uk.amazonforum.com/s/question/0D56Q0000B8xSlSSQU/using-manage-your-content-and-devices-to-remove-bulk-items-reversibly) |
| Brazil (`amazon.com.br`) | Same page, in Portuguese: **Gerencie seu conteúdo e dispositivos**. Amazon BR serves the same help nodes (same `nodeId`s) translated. Bulk steps: tick items or **Selecionar Tudo** → **Excluir** → **Sim**. | [Exclua eBooks do leitor eletrônico Kindle](https://www.amazon.com.br/gp/help/customer/display.html?nodeId=TIEM9w0fUmk2jXEknD), [Desativar o arquivamento (BR)](https://www.amazon.com.br/gp/help/customer/display.html?nodeId=G6N7P2TFA2YTH5YW); bulk steps **community**: [Oficina da Net](https://www.oficinadanet.com.br/amazon/36450-excluir-livros-biblioteca-kindle) |

**Use the store your Kindle is registered to.** A Brazilian account's library lives on `amazon.com.br`. **Unverified:** whether `amazon.com/mycd` shows a `.com.br` account's library. No source was found either way.

**Search box:** to narrow the list to BiteSIze, search for `News Digest` or `Resumo de Notícias` (the titles BiteSIze sends, `ai_locale.py`). **Unverified:** that mycd matches on title substrings. No Amazon page documents its search.

---

## 2. On the Kindle e-reader

Current firmware for 2024 Paperwhite / Colorsoft / Kindle is **5.20.1** ([Kindle E-Reader Software Updates](https://www.amazon.com/gp/help/customer/display.html?nodeId=GKMQC26VQQMM8XSW), fetched 31 Oct 2026).

| Action | Effect | Bulk? | Source |
|---|---|---|---|
| Item menu → **Remove download** | Frees space. The item stays in the cloud and can be downloaded again. | One item. Long-press on a collection also offers it. | [Remove Books from Your Kindle E-Reader](https://www.amazon.com/gp/help/customer/display.html?nodeId=TIEM9w0fUmk2jXEknD) |
| Item menu → **Permanently delete** | Removes from cloud **and all devices**. | One item. | Same page |
| **Storage management → Manual Removal** | Select items by type: Books, Audiobooks, Periodicals, **Docs**, Samples, Others. Removes downloads. | **Yes**, this is the on-device bulk path. | [Kindle User Guide (11th gen)](https://d1ergij2b6wmg5.cloudfront.net/kug/kindle_11th/v1/en-US/html/kug.html) |
| **Storage management → Quick Archive** | Removes downloads not opened recently (1 month to 1 year). | Yes, by age. | Same guide; [Good e-Reader](https://goodereader.com/blog/kindle/kindle-quick-archive-now-more-accessible-post-new-software-update-can-let-you-free-some-storage) |

**Re-download:** items removed with Remove download, Manual Removal, or Quick Archive stay in the cloud under **All** ([Kindle User Guide](https://d1ergij2b6wmg5.cloudfront.net/kug/kindle_11th/v1/en-US/html/kug.html)). They are not downloaded again unless you open them. **Unverified:** whether a sync with archiving on ever re-pushes removed docs on its own. No source says so.

**USB-copied files are different:** "The Cloud doesn't store files that you transferred to your Kindle using the USB cable. When you remove them from the device, you permanently delete them." ([Amazon](https://www.amazon.com/gp/help/customer/display.html?nodeId=TIEM9w0fUmk2jXEknD))

**Collections:** deleting a collection does not delete its contents from the device or the cloud ([Kindle User Guide](https://d1ergij2b6wmg5.cloudfront.net/kug/kindle_11th/v1/en-US/html/kug.html)). A collection can group digests. It cannot delete them.

---

## 3. USB / MTP deletion from a Mac

### Which Kindles need what

Amazon: "Kindle Scribe and 2024-released Kindle devices require a separate application" on macOS. Older models mount as a normal drive. ([Connect, Browse, and Transfer Files on E-Reader](https://www.amazon.com/gp/help/customer/display.html?nodeId=TCUBEdEkbIhK07ysFu)) The reason is that 2024 models use MTP, and macOS has no MTP driver ([Android Authority, Oct 2024](https://www.androidauthority.com/2024-kindle-sideloading-3494778/)).

| Tool | Delete on device? | Notes | Source |
|---|---|---|---|
| **Send to Kindle for Mac → Tools → USB File Manager** (Amazon) | Yes. Right-click → Delete, or Command+Delete. | macOS 12+. Drag and drop only; at most 2,000 files per transfer. Close other USB/MTP apps first. | [Amazon TCUBEdEkbIhK07ysFu](https://www.amazon.com/gp/help/customer/display.html?nodeId=TCUBEdEkbIhK07ysFu), [Send to Kindle Mac](https://www.amazon.com/sendtokindle/mac) |
| **OpenMTP** (open source, MIT) | Yes (file manager) | Lists Kindle Paperwhite, Colorsoft, Scribe as supported. `brew install --cask openmtp`. | [OpenMTP site](https://openmtp.ganeshrvel.com/), [GitHub](https://github.com/ganeshrvel/openmtp) |
| **Calibre** device view | Yes. Select books in the Device view → **Remove books** deletes them from the device. Ctrl/Shift-click to multi-select. | Only one program may hold the MTP device at a time; quit OpenMTP / Send to Kindle first. Mac + 2024 Kindle detection is flaky in reports. | [Calibre GUI manual](https://manual.calibre-ebook.com/gui.html); **community:** [MobileRead thread, Nov 2024 (Kovid Goyal: make sure calibre is the only MTP program)](https://www.mobileread.com/forums/showthread.php?p=4470957) |
| Android File Transfer (Google) | Yes | Google discontinued it in 2024 (**unverified**, third-party claim). Not recommended. | [ereadersforum guide](https://www.ereadersforum.com/blog/how-to-transfer-files-between-a-kindle-and-a-mac-in-2025-complete-guide/) |

### What to delete over USB

- Send-to-Kindle docs sit in the device's `documents` folder. **Unverified:** the exact file names Amazon gives converted Send-to-Kindle EPUBs on 5.20 firmware. Check before deleting in bulk.
- Each book can have a sibling **`<name>.sdr`** folder (sidecar: reading position, annotations, indexes). Deleting a book on the device leaves the `.sdr` behind on purpose. Delete it together with the book when you remove files over USB. (**Community:** [MobileRead: leftover folders](https://www.mobileread.com/forums/showthread.php?t=211384), [MobileRead: ghost sidecar folders](https://www.mobileread.com/forums/showthread.php?t=279304))
- Deleting over USB only touches the device. Cloud copies remain, and they come back if you open them from **All**. Do the mycd cleanup ([§1](#1-manage-your-content-and-devices-mycd)) first.

---

## 4. Personal Document Archiving

Path: mycd → **Preferences** → **Personal Document Settings** → **Personal Document Archiving** → **Edit Archive Settings** → untick **Enable personal document archiving to my Kindle library** → **Update**. Effect in Amazon's words: it stops "automatic storage of documents in Manage Your Content and Devices." ([Disable Document Archiving](https://www.amazon.com/gp/help/customer/display.html?nodeId=G6N7P2TFA2YTH5YW); BR: [same node on .com.br](https://www.amazon.com.br/gp/help/customer/display.html?nodeId=G6N7P2TFA2YTH5YW))

Implications:

- It affects **future** documents only. Existing ones stay until deleted ([2026-08-30 note](2026-08-30-kindle-auto-delete.md#decision-relevant-finding)).
- Documents then live only on the device they were emailed to. Removing them on that device loses them for good. An Amazon BR forum staff reply warns that personal documents sent only to one Kindle may be lost when that device is deregistered (**community:** [Amazon BR forum](https://amazonforum.my.site.com/BR/s/question/0D56Q0000CJD3IfSQL/como-excluir-um-dispositivo)).
- **Unverified:** whether reading position and highlights still sync for non-archived docs, and whether the Kindle phone apps still receive them. Amazon does not say. The Web uploader's guidance ("turn on Add to your library so that you can download documents in your library to any device") suggests cross-device access depends on archiving ([Learn About Sending Documents](https://www.amazon.com/gp/help/customer/display.html?nodeId=G28WHGXBEXT6QSXY)).
- With archiving off, on-device **Manual Removal → Docs** ([§2](#2-on-the-kindle-e-reader)) becomes a complete cleanup, because no cloud copy exists. This follows from the two Amazon pages above; it is not stated by Amazon.

---

## 5. Automation and app-side mitigations

### Is there a supported way to automate deletion?

**No.** There is no public consumer API for deleting Kindle personal documents. Scripting the private mycd endpoints conflicts with Amazon's Conditions of Use. See the [2026-08-30 note §2 and §6](2026-08-30-kindle-auto-delete.md#2-remote-deletion--website-apps-api). Unofficial tools exist. [Kindle_download_helper](https://github.com/yihong0618/Kindle_download_helper) downloads documents (it does not delete them) using a browser cookie and a CSRF token. That approach stays out of scope.

### Does Send to Kindle replace a document with the same title?

**No evidence that it does. Reports say it creates a duplicate.** Amazon has no help page on this.

- MobileRead, April 2024: a user emailing an updated file gets "2 versions of the file on the kindle". The reply recommends USB + Calibre to replace files (**community:** [MobileRead t=360252](https://www.mobileread.com/forums/showthread.php?t=360252)).
- Amazon forum: emailing the same document twice produced a duplicate (**community:** [renaming personal document title](https://www.amazonforum.com/s/question/0D54P00006zJ7qFSAS/renaming-personal-document-title); [Duplicate Books Through Email Transfer](https://www.amazonforum.com/s/question/0D54P00006zIpIfSAK/duplicate-books-through-email-transfer)).

So a **fixed filename/title would not make a new digest replace the old one.** It would only produce many items with the same name. **Unverified:** which field Amazon uses as the library title for emailed EPUBs. Reports conflict between the attachment filename and the EPUB `dc:title` ([KBoards](https://www.kboards.com/threads/adding-epubs-to-kindle-with-cover-art-and-other-metadata.339089/), [MobileRead t=333506](https://www.mobileread.com/forums/showthread.php?t=333506)). BiteSIze sets both, with different formats:

| Field | Code | Value today |
|---|---|---|
| Attachment filename | `kindle.py` `send_to_kindle`: `filename=epub_path.name` (from `main.py:285`) | `News Digest - October 30 2026 0651.epub` |
| Email subject | `kindle.py`: `msg["Subject"] = epub_path.stem` | `News Digest - October 30 2026 0651` |
| EPUB title / identifier | `epub.py:766-767`: `set_identifier(f"bitesize-{%Y%m%d%H%M%S}")`, `set_title(f"{digest} – {date} {HH:MM}")` | unique per run |

### Practical mitigations BiteSIze could implement (proposals, not shipped)

| Idea | Where | Effect | Grounding |
|---|---|---|---|
| **Keep dated, sortable names** | `main.py:285` | Old digests are easy to find and tick in mycd. A fixed name gives no replacement ([above](#does-send-to-kindle-replace-a-document-with-the-same-title)). | Community duplicate reports |
| **Opt-in iCloud Books retention** (keep newest N `{digest_title} - *.epub`) | `books.py`, next to `copy_to_icloud_books`, using `resolve_icloud_books_dir` | Bounds the Apple Books backlog. BiteSIze owns these files. | **Unverified:** that deleting a file from `~/Library/Mobile Documents/iCloud~com~apple~iBooks/Documents` removes it from the Books library on every device. Apple documents only in-app removal ([§6](#6-apple-books-icloud-copies)). Test on one file first. |
| **Opt-in `output/` retention** | `main.py` after step 8 | Local disk only. | Already marked KEEP in the [2026-08-30 note §6](2026-08-30-kindle-auto-delete.md#6-practical-recommendation-for-bitesize) |
| **Dashboard reminder** with the mycd Docs link for the user's store (`.com` / `.com.br`) | `dashboard.py` | Puts the manual step one click away. | §1 |
| Fixed Kindle collection | — | **Not possible by email.** No documented way to assign a collection from Send to Kindle. Collections only group items; they do not delete them. | [2026-08-30 note §4](2026-08-30-kindle-auto-delete.md#collections); [Kindle User Guide](https://d1ergij2b6wmg5.cloudfront.net/kug/kindle_11th/v1/en-US/html/kug.html) |
| Script mycd deletes | — | **DROP** (ToS, fragile) | [2026-08-30 note](2026-08-30-kindle-auto-delete.md) |

---

## 6. Apple Books (iCloud copies)

BiteSIze writes into the iCloud Books folder (`books.py` `_CANDIDATE_DIRS`). Apple syncs imported EPUBs and PDFs through iCloud Drive, with Books enabled under iCloud Drive on every device ([Set up iCloud for Apple Books](https://support.apple.com/guide/icloud/set-up-books-mm3941ae3362/icloud), [If Books isn't syncing](https://support.apple.com/en-us/118661)). The backlog also uses iCloud storage.

| Platform | Steps | Source |
|---|---|---|
| **Mac** | Books → a collection under Library → **More (…)** on the item → **Remove** → choose an option (Remove Download keeps the item visible; Remove Everywhere / Delete remove it). | [Delete books or audiobooks from your Mac in Books](https://support.apple.com/guide/books/delete-books-or-audiobooks-ibks67184a3a/mac) |
| **iPhone / iPad** | Book → **More** below the cover → **Remove** → choose an option. | [Organize books in the Books app on iPhone](https://support.apple.com/guide/iphone/organize-books-iphab219b91/ios) |
| Automatic | **Remove Downloads → Automatically When Finished** frees device space only. It does not delete from iCloud. | Same two pages |

**Bulk select:** Apple's current pages describe only per-item removal. **Unverified:** Command/Shift-click multi-select followed by Delete in Books on Mac. Older Books 4.1 documented **Edit → Delete** from the menu bar on a selection ([Books 4.1 on macOS 12](https://support.apple.com/en-qa/guide/books/ibks67184a3a/4.1/mac/12.0)). A practical tip is to put digests in a dedicated Books collection so they are easy to find. No Apple source says this speeds up deletion.

---

## Sources

**Amazon (primary)**

- [Remove Books from Your Kindle E-Reader](https://www.amazon.com/gp/help/customer/display.html?nodeId=TIEM9w0fUmk2jXEknD) · [BR](https://www.amazon.com.br/gp/help/customer/display.html?nodeId=TIEM9w0fUmk2jXEknD)
- [Disable Document Archiving in Your Kindle Library](https://www.amazon.com/gp/help/customer/display.html?nodeId=G6N7P2TFA2YTH5YW) · [BR](https://www.amazon.com.br/gp/help/customer/display.html?nodeId=G6N7P2TFA2YTH5YW)
- [Learn About Sending Documents to Your Kindle Library](https://www.amazon.com/gp/help/customer/display.html?nodeId=G28WHGXBEXT6QSXY)
- [Learn How to Use Your Send to Kindle Email Address](https://www.amazon.com/gp/help/customer/display.html?nodeId=G7NECT4B4ZWHQ8WV)
- [Connect, Browse, and Transfer Files on E-Reader](https://www.amazon.com/gp/help/customer/display.html?nodeId=TCUBEdEkbIhK07ysFu)
- [Remove Personal Documents from Kindle for Windows](https://www.amazon.com/gp/help/customer/display.html?nodeId=TEYEjk3h6UBK0eAr0c)
- [Kindle E-Reader Software Updates](https://www.amazon.com/gp/help/customer/display.html?nodeId=GKMQC26VQQMM8XSW)
- [Sync Your Kindle E-Reader](https://www.amazon.com/gp/help/customer/display.html?nodeId=GDCAMDFMC2LZP6BR)
- [Kindle User Guide (11th gen, HTML)](https://d1ergij2b6wmg5.cloudfront.net/kug/kindle_11th/v1/en-US/html/kug.html)
- [Send to Kindle for Mac](https://www.amazon.com/sendtokindle/mac)

**Apple (primary)**

- [Delete books or audiobooks from your Mac in Books](https://support.apple.com/guide/books/delete-books-or-audiobooks-ibks67184a3a/mac)
- [Organize books in the Books app on iPhone](https://support.apple.com/guide/iphone/organize-books-iphab219b91/ios)
- [Set up iCloud for Apple Books](https://support.apple.com/guide/icloud/set-up-books-mm3941ae3362/icloud)
- [If the Apple Books app isn't syncing across devices](https://support.apple.com/en-us/118661)

**Tools**

- [Calibre User Manual — GUI (Device view, Remove books)](https://manual.calibre-ebook.com/gui.html)
- [OpenMTP](https://openmtp.ganeshrvel.com/) · [GitHub](https://github.com/ganeshrvel/openmtp)

**Community / articles (secondary)**

- [MobileRead: Can I email to kindle and overwrite a doc? (2024)](https://www.mobileread.com/forums/showthread.php?t=360252)
- [MobileRead: Paperwhite 2024 not recognised by Calibre (2024)](https://www.mobileread.com/forums/showthread.php?p=4470957)
- [MobileRead: leftover .sdr folders](https://www.mobileread.com/forums/showthread.php?t=211384) · [ghost sidecar folders](https://www.mobileread.com/forums/showthread.php?t=279304)
- [Android Authority: 2024 Kindle sideloading explained](https://www.androidauthority.com/2024-kindle-sideloading-3494778/)
- [Amazon UK forum: bulk remove in Manage Your Content](https://uk.amazonforum.com/s/question/0D56Q0000B8xSlSSQU/using-manage-your-content-and-devices-to-remove-bulk-items-reversibly)
- [Oficina da Net: excluir livros da biblioteca Kindle (pt-BR)](https://www.oficinadanet.com.br/amazon/36450-excluir-livros-biblioteca-kindle)
- [Trusted Reviews: remove all books from a Kindle online](https://www.trustedreviews.com/how-to/how-to-remove-all-your-books-from-a-kindle-online-4289146)
- [Good e-Reader: Quick Archive](https://goodereader.com/blog/kindle/kindle-quick-archive-now-more-accessible-post-new-software-update-can-let-you-free-some-storage)
