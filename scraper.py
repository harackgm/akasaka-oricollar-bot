import os
import time
import random
import json
import requests
from bs4 import BeautifulSoup

# ==========================================
# 0. テストモード設定
# ==========================================
# Trueにすると実際のスクレイピングをスキップし、LINE通知テスト（デザイン確認）のみを実行します。
# テスト完了後は必ず False に戻してください。
TEST_MODE = True

# ==========================================
# 1. 基本設定
# ==========================================
LINE_CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN', '')
LINE_USER_ID = os.environ.get('LINE_USER_ID', '')

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'akasaka_items.json')

START_URL = "https://fishing-akasaka.com/view/category/ct4"
BASE_URL = "https://fishing-akasaka.com"
MAX_NOTIFY_LIMIT = 5  # 大量通知ストッパー閾値

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
]

# ==========================================
# 2. 通知用関数 (LINE Flex Message / カルーセル表示)
# ==========================================
def send_line_flex_carousel(items_to_notify):
    """複数の商品を1つのカルーセルメッセージとして送信する"""
    if not LINE_CHANNEL_TOKEN or not LINE_USER_ID:
        print("LINE APIキーが未設定のため通知をスキップします。")
        return
    if not items_to_notify:
        return

    bubbles = []
    for item in items_to_notify:
        if item["notify_type"] == "new":
            header_text = "【新商品追加】"
            header_color = "#1DB446" # LINEグリーン
        else:
            header_text = "【再販開始】"
            header_color = "#FF334B" # レッド

        bubble = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": header_text,
                        "weight": "bold",
                        "color": header_color,
                        "size": "sm"
                    },
                    {
                        "type": "text",
                        "text": item["name"],
                        "weight": "bold",
                        "size": "md",
                        "wrap": True,
                        "margin": "md"
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#4682B4",
                        "action": {
                            "type": "uri",
                            "label": "商品を見る",
                            "uri": item["url"]
                        }
                    }
                ]
            }
        }
        bubbles.append(bubble)

    payload_data = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "flex",
                "altText": "アカサカ釣具 新着・再販情報",
                "contents": {
                    "type": "carousel",
                    "contents": bubbles
                }
            }
        ]
    }

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}"
    }

    try:
        response = requests.post(url, headers=headers, json=payload_data)
        response.raise_for_status()
        print("LINEへカルーセル通知を送信しました。")
    except Exception as e:
        print(f"LINEカルーセル通知エラー: {e}")

# ==========================================
# 3. スクレイピング処理
# ==========================================
def fetch_all_items():
    items = {}
    current_page = 1
    
    while True:
        url = f"{START_URL}?page={current_page}"
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"取得エラー ({url}): {e}")
            break

        soup = BeautifulSoup(response.text, 'html.parser')
        item_list = soup.find('ul', class_='item-list newitems-list')
        if not item_list:
            break

        for li in item_list.find_all('li'):
            name_tag = li.find('dt', class_='item-info-name')
            if not name_tag or not name_tag.find('a'):
                continue
            
            a_tag = name_tag.find('a')
            item_name = a_tag.text.strip()
            item_url = BASE_URL + a_tag['href']
            
            item_id = a_tag['href'].split('?')[0].split('/')[-1]

            price_tag = li.find('dd', class_='item-info-price')
            status = "in_stock"
            if price_tag and "SOLD OUT" in price_tag.text:
                status = "sold_out"

            items[item_id] = {
                "name": item_name,
                "url": item_url,
                "status": status
            }

        pager = soup.find('ul', class_='pager-wrap')
        next_page_exists = False
        if pager:
            for page_link in pager.find_all('li', class_='pager-list'):
                if str(current_page + 1) in page_link.text:
                    next_page_exists = True
                    break

        if next_page_exists:
            current_page += 1
            time.sleep(random.uniform(2.0, 5.0))
        else:
            break
            
    return items

# ==========================================
# 4. メイン処理（差分検知と安全装置）
# ==========================================
def main():
    # --- テストモード処理 ---
    if TEST_MODE:
        print("テストモードで実行します。指定の3商品をLINEに通知します。")
        test_items = [
            {
                "notify_type": "new",
                "name": "【オリカラ】ディープパラドックス KID グレムリン【メール便OK】",
                "url": "https://fishing-akasaka.com/view/item/000000000395"
            },
            {
                "notify_type": "restock",
                "name": "【オリカラ】ディープパラドックス グラビティ ドッポ【10枚までメール便OK】",
                "url": "https://fishing-akasaka.com/view/item/000000000392"
            },
            {
                "notify_type": "new",
                "name": "【オリカラ】ラッキークラフト ワウ33S(ふわう) 赤坂グリ子【メール便OK】",
                "url": "https://fishing-akasaka.com/view/item/000000000400"
            }
        ]
        send_line_flex_carousel(test_items)
        return
    # ------------------------

    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            old_db = json.load(f)
    else:
        old_db = {}
        print("初回起動：データベースを新規作成します。")

    current_items = fetch_all_items()
    if not current_items:
        print("商品データが取得できませんでした。")
        return

    notify_list = []

    for item_id, item_data in current_items.items():
        if item_id not in old_db:
            if item_data["status"] == "in_stock":
                notify_list.append({
                    "notify_type": "new",
                    "name": item_data['name'],
                    "url": item_data['url']
                })
        else:
            old_status = old_db[item_id]["status"]
            if old_status == "sold_out" and item_data["status"] == "in_stock":
                notify_list.append({
                    "notify_type": "restock",
                    "name": item_data['name'],
                    "url": item_data['url']
                })

    if len(notify_list) > MAX_NOTIFY_LIMIT:
        print(f"※安全装置作動※ 検知数が{len(notify_list)}件に達したため、通知をスキップしDBのみ更新します。")
    elif len(notify_list) > 0:
        send_line_flex_carousel(notify_list)
        time.sleep(random.uniform(1.0, 2.0))
    else:
        print("新規の販売・再販はありませんでした。")

    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(current_items, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
