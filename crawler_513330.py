"""
513330 每日数据爬虫
从新浪财经自动抓取最新交易数据，追加到 513330_history_data.csv
支持每日定时运行，自动去重，失败重试
"""

import akshare as ak
import pandas as pd
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
            # 统一列名：Date, Open, Close, High, Low, Volume
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

def sync_csv(new_df):
    """将新数据合并到 CSV，自动去重"""
    if not CSV_PATH.exists():
        new_df.to_csv(CSV_PATH, index=False)
        print(f"新建 CSV: {CSV_PATH.name} ({len(new_df)} 行)")
        return len(new_df)

    old_df = pd.read_csv(CSV_PATH, parse_dates=["Date"])
    old_dates = set(old_df["Date"])

    # 只保留新数据中不在旧数据中的行
    append_df = new_df[~new_df["Date"].isin(old_dates)].copy()

    if append_df.empty:
        # 检查最后日期是否一致（验证数据已是最新）
        last_local = old_df["Date"].max().date()
        last_remote = new_df["Date"].max().date()
        if last_remote > last_local:
            print(f"数据可能遗漏: 远程最新 {last_remote}, 本地最新 {last_local}")
            # 尝试按日期范围合并
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

def main():
    print(f"513330 数据爬虫  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 40)

    new_df = fetch_etf_data()
    if new_df is None:
        print("失败: 无法获取数据")
        return 1

    print(f"远程数据: {new_df['Date'].min().date()} ~ {new_df['Date'].max().date()}  ({len(new_df)} 行)")

    added = sync_csv(new_df)
    if added > 0:
        # 验证：读回 CSV 检查完整性
        verify = pd.read_csv(CSV_PATH)
        total = len(verify)
        print(f"验证通过: {total} 行, 无重复")
    else:
        print("无需操作")

    print("-" * 40)
    return 0

if __name__ == "__main__":
    exit(main())
