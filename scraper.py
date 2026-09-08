import os
import time
import random
import json
import requests
from bs4 import BeautifulSoup

# ==========================================
# 0. テストモード設定
# ==========================================
# 本番稼働のため False に設定（Trueにすると管理者のみにテスト送信されます）
TEST_MODE = False

# ==========================================
# 1. 基本設定
# ==========================================
LINE_CHANNEL_TOKEN = os.environ.get('LINE_CHANNEL_TOKEN', '')
LINE_USER_ID = os.environ.get('LINE_USER_ID', '')  # テスト動作用に必要

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'akasaka_items.json')

START_URL = "https://fishing-akasaka.com/view/category/ct4"
BASE_URL = "https://fishing-akasaka.com"
MAX_NOTIFY_LIMIT = 5  # 大量通知ストッパー閾値

# GitHub上のバナー画像のRaw URL
HEADER_IMAGE_URL = "https://raw.githubusercontent.com/harackgm/akasaka-oricollar-bot/main/akasakabana.jpg"

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
]

# ==========================================
# 2. 通知用関数 (LINE Flex Message / Push or Broadcast)
# ==========================================
def send_line_flex_carousel(items_to_notify, is_test=False):
    """複数の商品を1つのカルーセルメッセージとして送信する"""
    if not LINE_CHANNEL_TOKEN:
        print("LINE APIキーが未設定のため通知をスキップします。")
        return
    if not items_to_notify:
        return

    # LINEのキャッシュを破棄するための現在時刻タイムスタンプ
    current_ts = str(int(time.time()))
    header_img_cache_busted = f"{HEADER_IMAGE_URL}?v={current_ts}"

    bubbles = []
    for item in items_to_notify:
        if item["notify_type"] == "new":
            header_text = "【新商品追加】"
            header_color = "#1DB446"
        else:
            header_text = "【再販開始】"
            header_color = "#FF334B"

        # 商品画像のキャッシュバスティング（既に?が含まれるURLも考慮）
        base_img_url = item.get("img_url", "https://fishing-akasaka.com/images/default.jpg")
        separator = "&" if "?" in base_img_url else "?"
        item_img_cache_busted = f"{base_img_url}{separator}v={current_ts}"

        bubble = {
            "type": "bubble",
            "hero": {
                "type": "image",
                "url": header_img_cache_busted,
                "size": "full",
                "aspectRatio": "17:10",
                "aspectMode": "cover"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "image",
                        "url": item_img_cache_busted,
                        "size": "full",
                        "aspectRatio": "1:1",
                        "aspectMode": "cover",
                        "margin": "none"
                    },
                    {
                        "type": "text",
                        "text": header_text,
                        "weight": "bold",
                        "color": header_color,
                        "size": "sm",
                        "margin": "md"
                    },
                    {
                        "type": "text",
                        "text": item["name"],
                        "weight": "bold",
                        "size": "md",
                        "wrap": True,
                        "margin": "sm"
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
                        "color": "#1B6634",
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

    # テストモード時は自分のみ(Push)、本番時は全員(Broadcast)へ分岐
    if is_test:
        url = "https://api.line.me/v2/bot/message/push"
        payload_data = {
            "to": LINE_USER_ID,
            "messages": [
                {
                    "type": "flex",
                    "altText": "【テスト】アカサカ釣具 新着・再販情報",
                    "contents": {
                        "type": "carousel",
                        "contents": bubbles
                    }
                }
            ]
        }
    else:
        url = "https://api.line.me/v2/bot/message/broadcast"
        payload_data = {
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

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}"
    }

    try:
        response = requests.post(url, headers=headers, json=payload_data)
        response.raise_for_status()
        send_type = "個人(Push)" if is_test else "一斉送信(Broadcast)"
        print(f"LINEへ{send_type}を完了しました。")
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
            
            img_tag = li.find('img')
            img_url = img_tag['src'] if img_tag else ""
            
            item_id = a_tag['href'].split('?')[0].split('/')[-1]

            price_tag = li.find('dd', class_='item-info-price')
            status = "in_stock"
            if price_tag and "SOLD OUT" in price_tag.text:
                status = "sold_out"

            items[item_id] = {
                "name": item_name,
                "url": item_url,
                "img_url": img_url,
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
    # --- テストモード時の処理 ---
    if TEST_MODE:
        print("テストモードで実行します。指定のダミー商品を管理者のみに通知します。")
        test_items = [
            {
                "notify_type": "new",
                "name": "【オリカラ】ディープパラドックス KID グレムリン【メール便OK】",
                "url": "https://fishing-akasaka.com/view/item/000000000395",
                "img_url": "https://makeshop-multi-images.akamaized.net/akasakashop/itemimages/000000000395_cgw69co.jpg"
            }
        ]
        # is_test=True を渡すことで、全員ではなく管理者（LINE_USER_ID）にのみ送信される
        send_line_flex_carousel(test_items, is_test=True)
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
                    "url": item_data['url'],
                    "img_url": item_data.get('img_url', '')
                })
        else:
            old_status = old_db[item_id]["status"]
            if old_status == "sold_out" and item_data["status"] == "in_stock":
                notify_list.append({
                    "notify_type": "restock",
                    "name": item_data['name'],
                    "url": item_data['url'],
                    "img_url": item_data.get('img_url', '')
                })

    # 大量通知ストッパー：検知数が上限を超えた場合は通知スキップ
    if len(notify_list) > MAX_NOTIFY_LIMIT:
        print(f"※安全装置作動※ 検知数が{len(notify_list)}件に達したため、通知をスキップしDBのみ更新します。")
    elif len(notify_list) > 0:
        send_line_flex_carousel(notify_list, is_test=False)
        time.sleep(random.uniform(1.0, 2.0))
    else:
        print("新規の販売・再販はありませんでした。")

    # DBを最新状態に上書き保存
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(current_items, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
