import logging
import azure.functions as func
from functions.update_exchage_rates import update_exchange_rates

app = func.FunctionApp()

@app.schedule(schedule="0 0 0 * * *", arg_name="myTimer", run_on_startup=True,
              use_monitor=False) 
def update_currency_rates(myTimer: func.TimerRequest) -> None:
    """
    Timer trigger function to update currency exchange rates in Cosmos DB.
    Runs daily at midnight.
    """
    if myTimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Timer trigger function executed - updating currency exchange rates')
    
    try:
        # Call the update function
        updated_item = update_exchange_rates()
        
        logging.info(f"Timer trigger: Successfully updated currency rates. Item ID: {updated_item.get('id')}")
        logging.info(f"Timer trigger: Last update: {updated_item.get('time_last_update_utc', 'Unknown')}")
        logging.info(f"Timer trigger: Total currencies: {len(updated_item.get('conversion_rates', {}))}")
        
    except ValueError as e:
        logging.error(f"Timer trigger: Configuration or validation error: {str(e)}")
        
    except Exception as e:
        logging.error(f"Timer trigger: Error updating currency rates: {str(e)}")