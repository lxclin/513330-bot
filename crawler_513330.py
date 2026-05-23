"""
513330 每日数据爬虫
从新浪财经自动抓取历史+实时数据，追加到 513330_history_data.csv
支持盘中/盘后多时段运行，自动去重，失败重试
"""

import akshare as ak
import pandas as pd
import requests
import re
from pathlib import Path
from datetime import datetime, timedelta
import time

CSV_PATH = Path(__file__).parent / "513330_history_data.csv"


def fetch_etf_data(retries=3):
    """从新浪抓取 513330 全量历史数据"""
    for attempt in range(1, retries + 1):
        try:
            df = ak.fund_etf_hist_sina(symbol="sh513330")
            if df is None or df.empty:
                raise ValueError("空数据")
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            df = df.rename(columns={
                "date": "Date", "open": "Open", "close": "Close",
                "high": "High", "low": "Low", "volume": "Volume"
            })
            df = df[["Date", "Open", "Close", "High", "Low", "Volume"]]
            for col in ["Open", "Close", "High", "Low"]:
                df[col] = df[col].astype(float)
            df["Volume"] = df["Volume"].astype(int)
            return df
        except Exception as e:
            print(f"[{attempt}/{retries}] 抓取失败: {e}")
            if attempt < retries:
                wait = attempt * 3
                print(f"  等待 {wait}s 后重试...")
                time.sleep(wait)
    return None


def fetch_realtime_quote():
    """从新浪实时行情获取 513330 当前价"""
    url = "http://hq.sinajs.cn/list=sh513330"
    headers = {"Referer": "https://finance.sina.com.cn"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = "gbk"
        match = re.search(r'"(.+)"', resp.text)
        if not match:
            raise ValueError(f"无法解析实时数据: {resp.text[:100]}")
        fields = match.group(1).split(",")
        # 字段: 名称, 今开, 昨收, 当前价, 最高, 最低, ...
        # ETF 字段数可能少于个股，取前6个关键字段
        name = fields[0]
        price = float(fields[3]) if len(fields) > 3 else None
        high = float(fields[4]) if len(fields) > 4 else None
        low = float(fields[5]) if len(fields) > 5 else None
        open_ = float(fields[1]) if len(fields) > 1 else None
        prev_close = float(fields[2]) if len(fields) > 2 else None
        return {
            "name": name,
            "price": price,
            "open": open_,
            "high": high,
            "low": low,
            "prev_close": prev_close,
        }
    except Exception as e:
        print(f"  实时行情获取失败: {e}")
        return None


def sync_csv(new_df):
    """将新数据合并到 CSV，自动去重"""
    if not CSV_PATH.exists():
        new_df.to_csv(CSV_PATH, index=False)
        print(f"新建 CSV: {CSV_PATH.name} ({len(new_df)} 行)")
        return len(new_df)

    old_df = pd.read_csv(CSV_PATH, parse_dates=["Date"])
    old_dates = set(old_df["Date"])

    append_df = new_df[~new_df["Date"].isin(old_dates)].copy()

    if append_df.empty:
        last_local = old_df["Date"].max().date()
        last_remote = new_df["Date"].max().date()
        if last_remote > last_local:
            mask = new_df["Date"] > pd.Timestamp(last_local)
            append_df = new_df[mask].copy()
        if append_df.empty:
            print(f"已是最新 ({last_local}), 无需更新")
            return 0

    merged = pd.concat([old_df, append_df], ignore_index=True)
    merged = merged.sort_values("Date").drop_duplicates(subset="Date", keep="last").reset_index(drop=True)
    merged.to_csv(CSV_PATH, index=False)

    print(f"更新完成:")
    print(f"  新增: {len(append_df)} 行 ({append_df['Date'].min().date()} ~ {append_df['Date'].max().date()})")
    print(f"  总行: {len(merged)} 行")
    print(f"  最新: {merged['Date'].max().date()}  Close={merged['Close'].iloc[-1]:.3f}")
    return len(append_df)


def update_intraday(rt):
    """将实时报价写入 CSV 当天行（盘中更新）"""
    if rt is None or rt["price"] is None:
        return False

    today = pd.Timestamp.now().normalize()
    if not CSV_PATH.exists():
        return False

    df = pd.read_csv(CSV_PATH, parse_dates=["Date"])
    last = df["Date"].max()

    # 如果最新日期不是今天且今天还没数据，追加今天行
    if last < today:
        prev_close = float(df["Close"].iloc[-1])
        vol = int(df["Volume"].tail(5).mean())  # 用近5日均量估算
        open_price = rt["open"] if rt["open"] and rt["open"] > 0 else rt["price"]
        high_price = rt["high"] if rt["high"] and rt["high"] > 0 else rt["price"]
        low_price = rt["low"] if rt["low"] and rt["low"] > 0 else rt["price"]

        new_row = pd.DataFrame([{
            "Date": today,
            "Open": open_price,
            "Close": rt["price"],
            "High": high_price,
            "Low": low_price,
            "Volume": vol,
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv(CSV_PATH, index=False)
        print(f"  盘中更新: {today.date()} Open={open_price:.3f} Close={rt['price']:.3f}")
        return True

    # 如果今天已有数据，用实时价更新 Close/High/Low
    if last == today:
        idx = df.index[-1]
        updated = False
        if rt["price"] != df.loc[idx, "Close"]:
            df.loc[idx, "Close"] = rt["price"]
            updated = True
        if rt["high"] and rt["high"] > df.loc[idx, "High"]:
            df.loc[idx, "High"] = rt["high"]
            updated = True
        if rt["low"] and rt["low"] < df.loc[idx, "Low"]:
            df.loc[idx, "Low"] = rt["low"]
            updated = True
        if updated:
            df.to_csv(CSV_PATH, index=False)
            print(f"  盘中更新: {today.date()} Close→{rt['price']:.3f}")
        return updated

    return False


def main():
    now = datetime.now()
    hour = now.hour
    print(f"513330 数据爬虫  |  {now.strftime('%Y-%m-%d %H:%M:%S')}")
    if hour < 12:
        print(f"  [早盘] 11:00 盘中抓取")
    elif hour < 15:
        print(f"  [午盘] 14:00 盘中抓取")
    else:
        print(f"  [收盘] 15:30 收盘抓取")
    print("-" * 40)

    # 1. 抓取历史日线 + 同步 CSV
    new_df = fetch_etf_data()
    if new_df is None:
        print("失败: 无法获取历史数据")
        return 1
    print(f"远程数据: {new_df['Date'].min().date()} ~ {new_df['Date'].max().date()}  ({len(new_df)} 行)")
    sync_csv(new_df)

    # 2. 抓取实时行情 + 更新当天行
    rt = fetch_realtime_quote()
    if rt and rt["price"]:
        print(f"实时行情: {rt['name']} 现价={rt['price']:.3f}  昨收={rt.get('prev_close', 'N/A')}")
        update_intraday(rt)
    else:
        print("实时行情: 未获取到 (可能非交易时段)")

    # 3. 验证
    verify = pd.read_csv(CSV_PATH, parse_dates=["Date"])
    print(f"CSV 总计: {len(verify)} 行, 最新: {verify['Date'].max().date()}")
    print("-" * 40)
    return 0


if __name__ == "__main__":
    exit(main())
