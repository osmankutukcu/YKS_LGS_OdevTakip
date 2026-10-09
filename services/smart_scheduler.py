# -*- coding: utf-8 -*-
"""
Smart Scheduler & AI Recommendation Engine
------------------------------------------
Advanced algorithms for student homework planning and performance prediction.
Features:
1. Weighted Subject Selection (Adaptive Learning)
2. Spaced Repetition Scheduling (Forgetting Curve Approximation)
3. Performance Trend Analysis (Linear Regression)
"""

import math
import random
import datetime
from typing import List, Dict, Tuple, Optional

def weighted_subject_recommendation(
    con, 
    student_id: int, 
    limit: int = 5
) -> List[Dict[str, float]]:
    """
    Suggests subjects based on weighted probability.
    Weak subjects have HIGHER probability of being suggested.
    
    Algorithm:
    1. Calculate success ratio per subject.
    2. Weight = 100 - SuccessRatio (lower success -> higher weight).
    3. Add 'staleness' bonus (subjects not done in a while get boost).
    4. Random sampling based on weights.
    """
    cursor = con.cursor()
    
    # 1. Fetch Performance Stats
    # (Simplified query to get success ratio per subject)
    sql_stats = """
        SELECT ders, 
               SUM(CASE WHEN lower(durum) IN ('yapildi','tamam','tamamlandı') THEN 1 ELSE 0 END) as bitti,
               COUNT(*) as toplam,
               MAX(tarih) as son_tarih
        FROM odev_satir
        WHERE ogrenci_id = ?
        GROUP BY ders
    """
    rows = cursor.execute(sql_stats, (student_id,)).fetchall()
    
    weights = {}
    today = datetime.date.today()
    
    for r in rows:
        ders = r['ders']
        bitti = r['bitti']
        toplam = r['toplam']
        son_tarih_str = r['son_tarih']
        
        # Calculate Success Ratio
        if toplam > 0:
            ratio = (bitti / toplam) * 100.0
        else:
            ratio = 50.0 # Neural start
            
        # Base Weight: Inverse of success (Failure rate)
        weight = max(10, 100 - ratio) 
        
        # Staleness Bonus (Forgetting Curve Simulation)
        # If last homework was X days ago, increase likelihood of review
        if son_tarih_str:
            try:
                last_date = datetime.datetime.strptime(son_tarih_str, "%Y-%m-%d").date()
                days_diff = (today - last_date).days
                
                # Ebbinghaus Forgetting Curve approx: rapidly decays then plateaus
                # We want to catch them before they forget too much.
                # Boost weight if > 3 days
                if days_diff > 3:
                    weight += days_diff * 2 # Add 2 points per day
            except:
                pass
        else:
            # Never done this subject? High priority!
            weight += 50 
            
        weights[ders] = weight

    # Normalize weights to probabilities
    total_weight = sum(weights.values())
    if total_weight == 0: 
        return [] # No data
        
    recommendations = []
    
    # Roulette Wheel Selection
    subjects = list(weights.keys())
    probs = [w/total_weight for w in weights.values()]
    
    # Select N items (with replacement allowed if list is small, else without)
    try:
        if len(subjects) >= limit:
            selected = random.choices(subjects, weights=probs, k=limit)
             # Dedup while preserving order
            seen = set()
            dedup = []
            for s in selected:
                if s not in seen:
                    dedup.append(s)
                    seen.add(s)
            recommendations = dedup
        else:
             # Just return sorted by weight desc
             recommendations = sorted(subjects, key=lambda s: weights[s], reverse=True)
    except:
        recommendations = subjects[:limit]
        
    # Return detail format
    result = []
    for sub in recommendations:
        w = weights.get(sub, 0)
        result.append({"subject": sub, "priority_score": round(w, 2)})
        
    return result


def predict_next_week_performance(
    con, 
    student_id: int
) -> Dict[str, any]:
    """
    Simple Linear Regression to forecast next week's completion rate
    based on the last 5 weeks.
    """
    # 1. Get weekly stats
    sql = """
        SELECT strftime('%Y-%W', tarih) as hafta,
               COUNT(*) as task_count,
               SUM(CASE WHEN lower(durum) IN ('yapildi','tamam') THEN 1 ELSE 0 END) as done_count
        FROM odev_satir
        WHERE ogrenci_id = ?
        GROUP BY hafta
        ORDER BY hafta DESC
        LIMIT 6
    """
    rows = con.execute(sql, (student_id,)).fetchall()
    
    if len(rows) < 3:
        return {"trend": "insufficient_data", "forecast": None}
        
    # Prepare data for regression (X=WeekIndex, Y=CompletionRate)
    # Reverse rows to be chronological (Oldest -> Newest)
    data = rows[::-1]
    
    x_vals = []
    y_vals = []
    
    for i, r in enumerate(data):
        total = r['task_count']
        done = r['done_count']
        rate = (done / total * 100) if total > 0 else 0
        x_vals.append(i)
        y_vals.append(rate)
        
    # Linear Regression: y = mx + c
    n = len(x_vals)
    sum_x = sum(x_vals)
    sum_y = sum(y_vals)
    sum_xy = sum(x*y for x,y in zip(x_vals, y_vals))
    sum_xx = sum(x*x for x in x_vals)
    
    denominator = (n * sum_xx - sum_x * sum_x)
    if denominator == 0:
        slope = 0
    else:
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        
    intercept = (sum_y - slope * sum_x) / n
    
    # Forecast next week (index = n)
    next_x = n
    forecast_y = slope * next_x + intercept
    forecast_y = max(0, min(100, forecast_y)) # Clamp 0-100
    
    trend_desc = "flat"
    if slope > 2: trend_desc = "improving"
    elif slope < -2: trend_desc = "declining"
    
    return {
        "trend": trend_desc,
        "slope": round(slope, 2),
        "current_avg": round(sum_y/n, 2),
        "forecast_next_week": round(forecast_y, 1)
    }

