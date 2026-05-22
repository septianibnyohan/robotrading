from openbb import obb
import pandas as pd
from datetime import datetime, timedelta

def test_calendar():
    """
    Simple scratch script to test OpenBB Economic Calendar fetching.
    """
    print("Initializing OpenBB and fetching calendar...")
    
    # Define a 3-day window
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    
    try:
        # Fetching from 'nasdaq' provider as it's usually reliable and doesn't need a key
        calendar_data = obb.economy.calendar(
            start_date=start_date, 
            end_date=end_date, 
            provider="nasdaq"
        )
        
        df = calendar_data.to_df()

        print('calendar data:', df)
        
        if df.empty:
            print("No events found for the selected period.")
            return

        # OpenBB often returns the date as the index. Reset it to make 'date' a column.
        if 'date' not in df.columns:
            df = df.reset_index()

        print(f"\nSuccessfully fetched {len(df)} events.")
        
        # Filter for US high-impact (approximated by country in 'nasdaq' provider)
        # Check if 'country' column exists
        if 'country' in df.columns:
            us_events = df[df['country'] == 'United States'].head(10)
        else:
            us_events = df.head(10)
        
        print("\nTop 10 US Events:")
        columns_to_show = ['event', 'date', 'actual', 'consensus', 'previous']
        # Only show columns that exist
        available_cols = [c for c in columns_to_show if c in df.columns]
        print(us_events[available_cols])
        
    except Exception as e:
        print(f"Error fetching OpenBB data: {e}")

if __name__ == "__main__":
    test_calendar()
