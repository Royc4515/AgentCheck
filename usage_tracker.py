# usage_tracker.py
import json
import os

def log_model_usage(user_id, model_name):
    """
    מאזין וסופר כמה פעמים משתמש הפעיל כל מודל.
    שומר את הנתונים בקובץ אנליטיקה גלובלי.
    """
    file_path = "global_analytics.json"
    
    # 1. קריאת הנתונים ההיסטוריים (אם הקובץ קיים)
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            stats = json.load(f)
    else:
        stats = {}
        
    # 2. הוספת המשתמש אם הוא לא קיים במערכת
    if user_id not in stats:
        stats[user_id] = {"total_calls": 0, "models": {}}
        
    # 3. עדכון המונים (Counters)
    stats[user_id]["total_calls"] += 1
    
    # אם המודל לא קיים אצל המשתמש, נאתחל אותו ל-0
    if model_name not in stats[user_id]["models"]:
        stats[user_id]["models"][model_name] = 0
        
    stats[user_id]["models"][model_name] += 1
    
    # 4. שמירה חזרה לקובץ
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4)