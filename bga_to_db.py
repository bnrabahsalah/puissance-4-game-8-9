# -*- coding: utf-8 -*-
# ============================================================
# bga_to_db.py
# ============================================================

import sys
import json
import time
import re
import traceback
import importlib.util
from pathlib import Path
from urllib.parse import urlparse

from selenium import webdriver
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ============================================================
# CONFIGURATION
# ============================================================

GAME_ID = 1186
FINISHED = 1
CONFIANCE = 3

# Scrape toutes les tailles
ONLY_9X9 = False
STRICT_SIZE_CHECK = False

# Taille par défaut si non détectée
DEFAULT_ROWS_IF_UNKNOWN = 9
DEFAULT_COLS_IF_UNKNOWN = 9

# None = illimité
MAX_PLAYERS = None
MAX_TABLES_PER_PLAYER = None

SLEEP_SCROLL = 1.0
PAUSE_BETWEEN_PLAYERS = 0.4
PAUSE_BETWEEN_TABLES = 0.6

PAGELOAD_TIMEOUT = 60
GET_RETRIES = 3
GET_RETRY_DELAY = 2.0

BASE = "https://boardgamearena.com"

PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

OUT_DIR = PROJECT_DIR / "scraped_moves"
OUT_DIR.mkdir(exist_ok=True)

SCRAPED_TABLES_FILE = PROJECT_DIR / "scraped_tables.json"
SCRAPED_PLAYERS_FILE = PROJECT_DIR / "scraped_players.json"


# ============================================================
# ENCODING HELPERS
# ============================================================


def read_text_any_encoding(path: Path) -> str:
    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
    last_err = None

    for enc in encodings:
        try:
            return path.read_text(encoding=enc)
        except Exception as e:
            last_err = e

    raise last_err


def write_text_utf8(path: Path, text: str):
    path.write_text(text, encoding="utf-8", newline="\n")


# ============================================================
# CHARGEMENT DU MODULE DB
# ============================================================

BGA_IMPORT_OK = False
BGA_IMPORT_ERROR = None
import_bga_moves_fn = None


def load_bga_import():
    global BGA_IMPORT_OK, BGA_IMPORT_ERROR, import_bga_moves_fn

    try:
        bga_import_path = PROJECT_DIR / "bga_import.py"

        if not bga_import_path.exists():
            raise FileNotFoundError(f"Fichier introuvable: {bga_import_path}")

        spec = importlib.util.spec_from_file_location(
            "bga_import", str(bga_import_path)
        )
        if spec is None or spec.loader is None:
            raise ImportError("Impossible de créer le loader pour bga_import.py")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, "import_bga_moves"):
            raise AttributeError(
                "La fonction 'import_bga_moves' est absente de bga_import.py"
            )

        import_bga_moves_fn = module.import_bga_moves
        BGA_IMPORT_OK = True
        BGA_IMPORT_ERROR = None

    except Exception as e:
        BGA_IMPORT_OK = False
        BGA_IMPORT_ERROR = f"{type(e).__name__}: {e}"
        import_bga_moves_fn = None


load_bga_import()


# ============================================================
# PERSISTENCE
# ============================================================


def load_json_file(path: Path, default_value):
    if path.exists():
        try:
            raw = read_text_any_encoding(path)
            return json.loads(raw)
        except Exception as e:
            print(f"⚠️ Impossible de lire {path}: {e}")
    return default_value


def save_json_file(path: Path, data):
    try:
        write_text_utf8(path, json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"⚠️ Impossible d'écrire {path}: {e}")


def load_scraped_tables() -> dict:
    data = load_json_file(
        SCRAPED_TABLES_FILE,
        {"scraped": [], "imported": [], "failed": {}},
    )
    data.setdefault("scraped", [])
    data.setdefault("imported", [])
    data.setdefault("failed", {})
    return data


def save_scraped_tables(data: dict):
    save_json_file(SCRAPED_TABLES_FILE, data)


def load_scraped_players() -> dict:
    data = load_json_file(
        SCRAPED_PLAYERS_FILE,
        {"done": []},
    )
    data.setdefault("done", [])
    return data


def save_scraped_players(data: dict):
    save_json_file(SCRAPED_PLAYERS_FILE, data)


def mark_scraped(data: dict, tid: str):
    if tid not in data["scraped"]:
        data["scraped"].append(tid)


def mark_imported(data: dict, tid: str):
    if tid not in data["imported"]:
        data["imported"].append(tid)


def mark_failed(data: dict, tid: str, reason: str):
    safe_reason = str(reason).encode("utf-8", errors="replace").decode("utf-8")
    data["failed"][tid] = safe_reason


def already_scraped(data: dict, tid: str) -> bool:
    return tid in data["scraped"]


def mark_player_done(data: dict, pid: str):
    if pid not in data["done"]:
        data["done"].append(pid)


def player_already_done(data: dict, pid: str) -> bool:
    return pid in data["done"]


# ============================================================
# DRIVER
# ============================================================


def make_driver(headless=False):
    opts = Options()

    if headless:
        opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1400,900")
    else:
        opts.add_argument("--start-maximized")

    opts.add_argument("--disable-notifications")
    opts.add_argument("--disable-popup-blocking")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-extensions")

    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(PAGELOAD_TIMEOUT)
    return driver


def safe_quit(driver):
    if driver is None:
        return
    try:
        driver.quit()
    except Exception as e:
        print(f"⚠️ driver.quit() failed: {e}")


def rebuild_driver(old_driver, headless=False):
    safe_quit(old_driver)
    print("♻️ Recréation du driver Selenium...")
    new_driver = make_driver(headless=headless)
    login_bga_manual(new_driver)
    return new_driver


def safe_get(driver, url, retries=GET_RETRIES, delay=GET_RETRY_DELAY):
    last_exc = None

    for attempt in range(1, retries + 1):
        try:
            if driver.session_id is None:
                raise WebDriverException("Session Selenium perdue")

            driver.get(url)
            return True

        except (TimeoutException, WebDriverException, ConnectionResetError) as e:
            last_exc = e
            print(f"⚠️ GET failed ({attempt}/{retries}) {url} -> {e}")

            if attempt < retries:
                time.sleep(delay)

    if last_exc is not None:
        raise last_exc

    return False


# ============================================================
# LOGIN
# ============================================================


def login_bga_manual(driver):
    global BASE

    print("🔐 Login manuel BGA...")
    safe_get(driver, f"{BASE}/account")

    input("Connecte-toi puis appuie ENTER... ")

    u = urlparse(driver.current_url)
    if u.scheme and u.netloc:
        BASE = f"{u.scheme}://{u.netloc}"

    print("BASE =", BASE)


# ============================================================
# HELPERS REPLAY / FIN DE LISTE
# ============================================================


def is_replay_limit_reached(driver):
    try:
        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
    except Exception:
        return False

    patterns = [
        "vous avez atteint une limite",
        "vous avez atteint une limite (replay)",
        "limite replay",
        "replay limit",
        "you have reached a limit",
        "you have reached a replay limit",
    ]
    return any(p in page_text for p in patterns)


def no_more_results_visible(driver):
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
    except Exception:
        return False

    patterns = [
        "pas d'autre résultat",
        "pas d'autres résultats",
        "no more results",
        "no other result",
    ]
    return any(p in body_text for p in patterns)


# ============================================================
# PLAYER COLLECTION
# ============================================================


def collect_visible_players_from_ranking(driver):
    players = []
    seen = set()

    selectors = [
        'a[href*="/player?id="]',
        'a[href*="player?id="]',
    ]

    for selector in selectors:
        try:
            anchors = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            anchors = []

        for a in anchors:
            try:
                href = a.get_attribute("href") or ""
                m = re.search(r"(?:/player\?id=|player\?id=)(\d+)", href)
                if not m:
                    continue

                pid = m.group(1)

                pseudo = (a.text or "").strip()
                if not pseudo:
                    pseudo = (a.get_attribute("innerText") or "").strip()
                if not pseudo:
                    pseudo = (a.get_attribute("title") or "").strip()
                if not pseudo:
                    pseudo = (a.get_attribute("aria-label") or "").strip()

                if not pseudo or pid in seen:
                    continue

                seen.add(pid)
                players.append((pid, pseudo))

            except StaleElementReferenceException:
                continue
            except Exception:
                continue

    return players


def get_next_player_from_ranking(driver, scraped_players_data):
    url = f"{BASE}/gamepanel?game=connectfour"
    safe_get(driver, url)

    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    time.sleep(2)

    stable_rounds = 0
    last_visible_count = 0
    round_idx = 0

    while True:
        round_idx += 1

        visible_players = collect_visible_players_from_ranking(driver)
        print(f"   ranking round {round_idx}: {len(visible_players)} joueurs visibles")

        for pid, pseudo in visible_players:
            if not player_already_done(scraped_players_data, pid):
                print(f"✅ prochain joueur trouvé: {pseudo} (id={pid})")
                return pid, pseudo

        current_count = len(visible_players)
        if current_count == last_visible_count:
            stable_rounds += 1
        else:
            stable_rounds = 0
            last_visible_count = current_count

        if stable_rounds >= 8:
            print("⚠️ Aucun nouveau joueur visible trouvé sur la page ranking")
            return None

        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        except Exception as e:
            print("Scroll error:", e)
            return None

        time.sleep(1.2)

        try:
            driver.execute_script("window.scrollBy(0, -300);")
            time.sleep(0.3)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        except Exception:
            pass

        time.sleep(SLEEP_SCROLL)


# ============================================================
# TABLE IDS / VOIR PLUS
# ============================================================


def extract_table_ids_from_page(driver):
    html = driver.page_source or ""
    raw = re.findall(r"(?:/table\?table=|table\?table=|[?&]table=)(\d+)", html)

    out = []
    seen = set()

    for t in raw:
        try:
            n = int(t)
            if n > 0:
                s = str(n)
                if s not in seen:
                    seen.add(s)
                    out.append(s)
        except Exception:
            pass

    return out


def click_voir_plus_if_present(driver):
    if no_more_results_visible(driver):
        return False

    xpaths = [
        "//a[contains(normalize-space(.), 'Voir plus')]",
        "//button[contains(normalize-space(.), 'Voir plus')]",
        "//span[contains(normalize-space(.), 'Voir plus')]",
        "//a[contains(normalize-space(.), 'Show more')]",
        "//button[contains(normalize-space(.), 'Show more')]",
        "//span[contains(normalize-space(.), 'Show more')]",
        "//a[contains(normalize-space(.), 'More')]",
        "//button[contains(normalize-space(.), 'More')]",
    ]

    for xp in xpaths:
        try:
            elems = driver.find_elements(By.XPATH, xp)
        except Exception:
            continue

        for el in elems:
            try:
                if not el.is_displayed():
                    continue

                txt = (el.text or "").strip().lower()
                if not any(k in txt for k in ["voir plus", "show more", "more"]):
                    continue

                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", el
                )
                time.sleep(0.4)

                try:
                    el.click()
                except (
                    ElementClickInterceptedException,
                    StaleElementReferenceException,
                ):
                    driver.execute_script("arguments[0].click();", el)

                time.sleep(1.0)

                if no_more_results_visible(driver):
                    return False

                return True

            except Exception:
                continue

    return False


def restore_gamestats_progress(driver, player_id, visible_done):
    url = f"{BASE}/gamestats?player={player_id}&game_id={GAME_ID}&finished={FINISHED}"
    safe_get(driver, url)

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    time.sleep(0.8)

    restore_rounds = 0
    max_restore_rounds = 8

    while restore_rounds < max_restore_rounds:
        now_ids = extract_table_ids_from_page(driver)

        # dès qu'on retrouve au moins une partie déjà vue, on considère que c'est suffisant
        if any(x in now_ids for x in visible_done):
            break

        clicked = click_voir_plus_if_present(driver)
        if not clicked:
            break

        time.sleep(0.6)
        restore_rounds += 1


# ============================================================
# GAMEREVIEW EXTRACTION
# ============================================================

SIZE_RE = re.compile(r"(\d{1,2})\s*[x×]\s*(\d{1,2})", re.IGNORECASE)


def detect_board_size_anchored(page_text):
    if not page_text:
        return None

    lower = page_text.lower()

    if "9x9" in lower or "9×9" in lower:
        return (9, 9)

    for line in page_text.splitlines():
        l = line.strip()
        if not l:
            continue

        ll = l.lower()

        anchored = (
            ("board" in ll and "size" in ll)
            or ("taille" in ll and "plateau" in ll)
            or ("grid" in ll and "size" in ll)
        )

        if not anchored:
            continue

        m = SIZE_RE.search(l)
        if m:
            r = int(m.group(1))
            c = int(m.group(2))
            if 4 <= r <= 20 and 4 <= c <= 20:
                return r, c

    return None


def _dedupe_consecutive_columns(cols):
    if not cols:
        return []

    cleaned = [cols[0]]
    for c in cols[1:]:
        if c != cleaned[-1]:
            cleaned.append(c)
    return cleaned


def extract_size_and_moves_from_gamereview(driver, table_id):
    url = f"{BASE}/gamereview?table={table_id}"

    print(f"[{table_id}] open gamereview")

    try:
        safe_get(driver, url)
    except Exception as e:
        print(f"[{table_id}] GET error:", e)
        return None, []

    try:
        WebDriverWait(driver, 12).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
    except TimeoutException:
        print(f"[{table_id}] page timeout")
        return None, []

    time.sleep(1.5)

    if is_replay_limit_reached(driver):
        raise RuntimeError("REPLAY_LIMIT_REACHED")

    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text or ""
    except Exception:
        body_text = ""

    try:
        page_html = driver.page_source or ""
    except Exception:
        page_html = ""

    full_text = body_text + "\n" + page_html

    size = detect_board_size_anchored(full_text)

    patterns = [
        r"column\s+(\d+)",
        r"colonne\s+(\d+)",
    ]

    moves = []
    move_id = 1

    for line in full_text.splitlines():

        for p in patterns:
            m = re.search(p, line, re.IGNORECASE)
            if m:
                col = int(m.group(1))

                moves.append(
                    {
                        "move_id": move_id,
                        "col": col,
                        "player_name": "",
                    }
                )

                move_id += 1
                break

    print(f"[{table_id}] moves detected =", len(moves))

    return size, moves


# ============================================================
# DB IMPORT
# ============================================================


def import_into_db(moves, save_name, rows, cols):
    if not BGA_IMPORT_OK or import_bga_moves_fn is None:
        raise RuntimeError(f"Import DB indisponible. Détail: {BGA_IMPORT_ERROR}")

    return import_bga_moves_fn(
        moves,
        rows=rows,
        cols=cols,
        confiance=CONFIANCE,
        save_name=save_name,
        starting_color="R",
    )


# ============================================================
# SCRAPING D'UNE TABLE
# ============================================================


def scrape_single_table(driver, tid, pseudo, scraped_data):
    print(f"[{tid}] step 1: start scrape_single_table")

    size = None

    print(f"[{tid}] step 2: before extract_size_and_moves_from_gamereview")
    review_size, moves = extract_size_and_moves_from_gamereview(driver, tid)
    print(f"[{tid}] step 3: after extract_size_and_moves_from_gamereview")

    if review_size is not None:
        size = review_size

    if ONLY_9X9:
        if size is None:
            if STRICT_SIZE_CHECK:
                print(f"[{tid}] skip size unknown")
                mark_failed(scraped_data, tid, "size_unknown")
                save_scraped_tables(scraped_data)
                return "failed"
            else:
                size = (DEFAULT_ROWS_IF_UNKNOWN, DEFAULT_COLS_IF_UNKNOWN)
        else:
            if size != (9, 9):
                print(f"[{tid}] skip review size {size}")
                mark_failed(scraped_data, tid, f"review_size_{size[0]}x{size[1]}")
                save_scraped_tables(scraped_data)
                return "skipped_non_9x9"
    else:
        if size is None:
            size = (DEFAULT_ROWS_IF_UNKNOWN, DEFAULT_COLS_IF_UNKNOWN)
            print(f"[{tid}] size unknown -> fallback {size[0]}x{size[1]}")
        else:
            print(f"[{tid}] size detected -> {size[0]}x{size[1]}")

    print(f"[{tid}] step 4: moves count = {len(moves)}")

    if not moves:
        try:
            body_preview = driver.find_element(By.TAG_NAME, "body").text[:1500]
            print("=== BODY TEXT PREVIEW ===")
            print(body_preview)
        except Exception:
            pass

        print(f"[{tid}] no moves")
        mark_failed(scraped_data, tid, "no_moves")
        save_scraped_tables(scraped_data)
        return "failed"

    rows, cols = size

    safe_pseudo = re.sub(r'[\\/:*?"<>|]+', "_", pseudo).strip() or "unknown"
    out_path = OUT_DIR / f"moves_{safe_pseudo}_{tid}.json"

    print(f"[{tid}] step 5: before write json")
    write_text_utf8(
        out_path,
        json.dumps(
            {
                "table_id": tid,
                "player": pseudo,
                "rows": rows,
                "cols": cols,
                "moves": moves,
            },
            indent=2,
            ensure_ascii=False,
        ),
    )
    print(f"[{tid}] step 6: after write json")

    print(f"[{tid}] step 7: before import_into_db")
    gid = import_into_db(
        moves=moves,
        save_name=f"BGA_{tid}_{rows}x{cols}",
        rows=rows,
        cols=cols,
    )
    print(f"[{tid}] step 8: after import_into_db id={gid}")

    mark_scraped(scraped_data, tid)
    mark_imported(scraped_data, tid)
    save_scraped_tables(scraped_data)

    print(f"[{tid}] step 9: done")
    return "imported"


# ============================================================
# SCRAPING D'UN JOUEUR
# ============================================================


def scrape_player_tables_incremental(driver, player_id, pseudo, scraped_data):
    url = f"{BASE}/gamestats?player={player_id}&game_id={GAME_ID}&finished={FINISHED}"
    safe_get(driver, url)

    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    time.sleep(2)

    visible_done = set()
    rounds_without_new = 0
    replay_limit_hit = False

    total_seen = 0
    total_skipped = 0
    total_imported = 0
    total_duplicate = 0
    total_failed = 0

    round_idx = 0

    while True:
        if replay_limit_hit:
            break

        round_idx += 1

        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        except Exception:
            pass

        time.sleep(1.0)

        if is_replay_limit_reached(driver):
            print("Replay limit reached on stats page.")
            replay_limit_hit = True
            break

        if no_more_results_visible(driver):
            print("End of results for this player.")
            break

        current_ids = extract_table_ids_from_page(driver)

        if (
            MAX_TABLES_PER_PLAYER is not None
            and len(current_ids) > MAX_TABLES_PER_PLAYER
        ):
            current_ids = current_ids[:MAX_TABLES_PER_PLAYER]

        new_ids = [tid for tid in current_ids if tid not in visible_done]

        print(
            f"   round {round_idx}: {len(current_ids)} tables visibles, {len(new_ids)} nouvelles"
        )

        if new_ids:
            rounds_without_new = 0
        else:
            rounds_without_new += 1

        for tid in new_ids:
            if replay_limit_hit:
                break

            visible_done.add(tid)
            total_seen += 1

            if already_scraped(scraped_data, tid):
                print(f"⏭️ table {tid} déjà scrapée, skip")
                total_skipped += 1
                continue

            print(f"🎯 scrape table {tid}")

            try:
                result = scrape_single_table(driver, tid, pseudo, scraped_data)

                if result == "imported":
                    total_imported += 1
                elif result == "duplicate":
                    total_duplicate += 1
                else:
                    total_failed += 1

                time.sleep(PAUSE_BETWEEN_TABLES)

                safe_get(
                    driver,
                    f"{BASE}/gamestats?player={player_id}&game_id={GAME_ID}&finished={FINISHED}",
                )
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                time.sleep(0.8)

                if is_replay_limit_reached(driver):
                    print("Replay limit reached after returning to stats.")
                    replay_limit_hit = True
                    break

                if no_more_results_visible(driver):
                    print("End of results for this player.")
                    break

            except KeyboardInterrupt:
                print("\n⛔ Interruption utilisateur")
                raise

            except Exception as e:
                if "REPLAY_LIMIT_REACHED" in str(e):
                    print("Replay limit reached. Stop scraping.")
                    replay_limit_hit = True
                    break

                safe_err = repr(e)
                print(f"Error on table {tid}: {safe_err}")
                traceback.print_exc()
                mark_failed(scraped_data, tid, f"{type(e).__name__}: {safe_err}")
                save_scraped_tables(scraped_data)
                total_failed += 1

                try:
                    driver = rebuild_driver(driver, headless=False)
                    restore_gamestats_progress(driver, player_id, visible_done)
                except Exception as rebuild_err:
                    print(f"❌ Rebuild driver failed: {rebuild_err}")
                    raise

        if replay_limit_hit:
            break

        if no_more_results_visible(driver):
            print("End of results for this player.")
            break

        clicked = click_voir_plus_if_present(driver)

        if clicked:
            print("   ➕ clic sur 'Voir plus'")
            time.sleep(1.5)
            continue

        if no_more_results_visible(driver):
            print("End of results for this player.")
            break

        if rounds_without_new >= 1:
            print("No new tables, stop.")
            break

    return {
        "driver": driver,
        "seen": total_seen,
        "skipped": total_skipped,
        "imported": total_imported,
        "duplicate": total_duplicate,
        "failed": total_failed,
    }


# ============================================================
# BOUCLE GLOBALE
# ============================================================


def main():
    scraped_data = load_scraped_tables()
    scraped_players_data = load_scraped_players()

    print(f"📋 Tables déjà scrapées : {len(scraped_data['scraped'])}")
    print(f"👤 Joueurs déjà traités : {len(scraped_players_data['done'])}")

    print("PROJECT_DIR =", PROJECT_DIR)
    print("bga_import exists =", (PROJECT_DIR / "bga_import.py").exists())

    if BGA_IMPORT_OK:
        print("✅ Module bga_import chargé")
    else:
        print(f"⚠️ Module bga_import indisponible: {BGA_IMPORT_ERROR}")

    driver = None

    total_seen = 0
    total_skipped = 0
    total_imported = 0
    total_duplicate = 0
    total_failed = 0

    try:
        try:
            driver = make_driver(headless=False)
        except Exception as e:
            print("Chrome start error:", e)
            return

        login_bga_manual(driver)

        while True:
            if (
                MAX_PLAYERS is not None
                and len(scraped_players_data["done"]) >= MAX_PLAYERS
            ):
                print("MAX_PLAYERS reached.")
                break

            print("\n" + "=" * 70)
            print("🔎 Recherche du prochain joueur à scraper...")
            print("=" * 70)

            next_player = get_next_player_from_ranking(driver, scraped_players_data)

            if next_player is None:
                print(
                    "😴 Aucun nouveau joueur trouvé. Nouvelle tentative dans 10 secondes..."
                )
                time.sleep(10)
                continue

            player_id, pseudo = next_player

            print("\n" + "=" * 60)
            print("PLAYER", pseudo, f"(id={player_id})")
            print("=" * 60)

            try:
                stats = scrape_player_tables_incremental(
                    driver=driver,
                    player_id=player_id,
                    pseudo=pseudo,
                    scraped_data=scraped_data,
                )

                driver = stats["driver"]

                total_seen += stats["seen"]
                total_skipped += stats["skipped"]
                total_imported += stats["imported"]
                total_duplicate += stats["duplicate"]
                total_failed += stats["failed"]

                mark_player_done(scraped_players_data, player_id)
                save_scraped_players(scraped_players_data)

            except KeyboardInterrupt:
                print("\n⛔ Arrêt demandé par l'utilisateur")
                raise

            except Exception as e:
                print(f"⚠️ Impossible de scraper les tables du joueur {pseudo}: {e}")
                traceback.print_exc()
                total_failed += 1

                try:
                    driver = rebuild_driver(driver, headless=False)
                except Exception as rebuild_err:
                    print(f"❌ Rebuild driver failed: {rebuild_err}")
                    return

            time.sleep(PAUSE_BETWEEN_PLAYERS)

    except KeyboardInterrupt:
        print("\n" + "=" * 50)
        print("ARRÊT PROPRE")
        print(f"  tables vues       : {total_seen}")
        print(f"  tables skippées   : {total_skipped}")
        print(f"  parties importées : {total_imported}")
        print(f"  doublons DB       : {total_duplicate}")
        print(f"  erreurs           : {total_failed}")
        print("=" * 50)

    finally:
        save_scraped_tables(scraped_data)
        save_scraped_players(scraped_players_data)
        safe_quit(driver)


# ============================================================

if __name__ == "__main__":
    main()
