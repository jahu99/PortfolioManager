"""Calibration CSV and Excel output."""
from pathlib import Path
import pandas as pd


def write_report(detail: pd.DataFrame, output_dir: Path, stem: str):
    output_dir.mkdir(parents=True, exist_ok=True)
    csv = output_dir / f'{stem}.csv'; xlsx = output_dir / f'{stem}.xlsx'
    detail.to_csv(csv, index=False)
    summary = detail.groupby('Miss Classification', dropna=False).agg(
        Count=('Ticker','size'), Avg_Forward_Return_28D=('Forward Return %','mean'),
        Median_Forward_Return_28D=('Forward Return %','median'),
        Positive_Rate=('Forward Return %', lambda s: (s > 0).mean()*100)
    ).reset_index()
    with pd.ExcelWriter(xlsx, engine='openpyxl') as writer:
        detail.to_excel(writer, sheet_name='Calibration Detail', index=False)
        summary.to_excel(writer, sheet_name='Miss Summary', index=False)
    return csv, xlsx
