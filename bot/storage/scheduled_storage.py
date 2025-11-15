"""Schedule interval and duration option storage operations."""
from typing import List, Dict
from bot.storage.database import Database


class ScheduledStorage:
    """Schedule interval and duration option storage operations."""
    
    def __init__(self, db: Database):
        """Initialize scheduled storage."""
        self.db = db
    
    def get_schedule_intervals(self) -> List[Dict]:
        """Get all active schedule intervals from database."""
        try:
            results = self.db.execute_query(
                """SELECT id, time, time_type, display_order
                   FROM schedule_intervals
                   WHERE is_active = TRUE
                   ORDER BY display_order, time""",
                fetch_all=True
            )
            intervals = []
            for row in results:
                # Convert to minutes for internal use
                time_value = row['time']
                time_type = row['time_type']
                if time_type == 'sekund':
                    minutes = time_value / 60.0
                elif time_type == 'minut':
                    minutes = time_value
                elif time_type == 'soat':
                    minutes = time_value * 60.0
                else:
                    minutes = time_value
                
                # Format display text
                time_unit = {
                    'sekund': 'sekund',
                    'minut': 'daqiqa',
                    'soat': 'soat'
                }.get(time_type, time_type)
                # Check if float is whole number
                if isinstance(time_value, float) and time_value.is_integer():
                    time_display = int(time_value)
                elif isinstance(time_value, (int, float)) and time_value == int(time_value):
                    time_display = int(time_value)
                else:
                    time_display = time_value
                display_text = f"{time_display} {time_unit}"
                
                intervals.append({
                    'id': row['id'],
                    'time': time_value,
                    'time_type': time_type,
                    'minutes': minutes,
                    'display_text': display_text,
                    'display_order': row['display_order']
                })
            return intervals
        except Exception as e:
            print(f"Error getting schedule intervals: {e}")
            # Return default intervals if table doesn't exist
            return [
                {'id': 1, 'time': 5, 'time_type': 'minut', 'minutes': 5, 'display_text': '5 daqiqa', 'display_order': 1},
                {'id': 2, 'time': 10, 'time_type': 'minut', 'minutes': 10, 'display_text': '10 daqiqa', 'display_order': 2},
                {'id': 3, 'time': 15, 'time_type': 'minut', 'minutes': 15, 'display_text': '15 daqiqa', 'display_order': 3},
                {'id': 4, 'time': 30, 'time_type': 'minut', 'minutes': 30, 'display_text': '30 daqiqa', 'display_order': 4},
                {'id': 5, 'time': 60, 'time_type': 'minut', 'minutes': 60, 'display_text': '1 soat', 'display_order': 5},
            ]
    
    def get_duration_options(self) -> List[Dict]:
        """Get all active duration options from database."""
        try:
            results = self.db.execute_query(
                """SELECT id, time, time_type, display_order
                   FROM duration_options
                   WHERE is_active = TRUE
                   ORDER BY display_order, time""",
                fetch_all=True
            )
            durations = []
            for row in results:
                # Convert to hours for internal use
                time_value = row['time']
                time_type = row['time_type']
                if time_type == 'sekund':
                    hours = time_value / 3600.0
                elif time_type == 'minut':
                    hours = time_value / 60.0
                elif time_type == 'soat':
                    hours = time_value
                else:
                    hours = time_value
                
                # Format display text
                time_unit = {
                    'sekund': 'sekund',
                    'minut': 'daqiqa',
                    'soat': 'soat'
                }.get(time_type, time_type)
                # Check if float is whole number
                if isinstance(time_value, float) and time_value.is_integer():
                    time_display = int(time_value)
                elif isinstance(time_value, (int, float)) and time_value == int(time_value):
                    time_display = int(time_value)
                else:
                    time_display = time_value
                display_text = f"{time_display} {time_unit}"
                
                durations.append({
                    'id': row['id'],
                    'time': time_value,
                    'time_type': time_type,
                    'hours': hours,
                    'display_text': display_text,
                    'display_order': row['display_order']
                })
            return durations
        except Exception as e:
            print(f"Error getting duration options: {e}")
            # Return default durations if table doesn't exist
            return [
                {'id': 1, 'time': 1, 'time_type': 'soat', 'hours': 1, 'display_text': '1 soat', 'display_order': 1},
                {'id': 2, 'time': 2, 'time_type': 'soat', 'hours': 2, 'display_text': '2 soat', 'display_order': 2},
                {'id': 3, 'time': 3, 'time_type': 'soat', 'hours': 3, 'display_text': '3 soat', 'display_order': 3},
                {'id': 4, 'time': 4, 'time_type': 'soat', 'hours': 4, 'display_text': '4 soat', 'display_order': 4},
                {'id': 5, 'time': 5, 'time_type': 'soat', 'hours': 5, 'display_text': '5 soat', 'display_order': 5},
            ]

