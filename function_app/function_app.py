import logging
import json
import azure.functions as func
from functions.update_exchage_rates import update_exchange_rates
from functions.exchange_currency import exchange_currency, get_supported_currencies

app = func.FunctionApp()

@app.schedule(schedule="0 0 0 * * *", arg_name="myTimer", run_on_startup=False,
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


@app.route(route="exchange-currency", auth_level=func.AuthLevel.FUNCTION, methods=["GET"])
def exchange_currency_http(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP endpoint to get exchange rate between two currencies.
    
    GET: /api/exchange-currency?from=USD&to=EUR
    
    Args:
        req: HTTP request object
        
    Returns:
        func.HttpResponse: JSON response with exchange rate information
    """
    logging.info('HTTP trigger function processed a currency exchange request')
    
    try:
        # Get parameters from query string
        from_currency = req.params.get('from')
        to_currency = req.params.get('to')
        
        if not from_currency or not to_currency:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": "Missing required parameters 'from' and 'to'",
                    "example": "/api/exchange-currency?from=USD&to=EUR"
                }),
                status_code=400,
                headers={"Content-Type": "application/json"}
            )
        
        # Call the exchange currency function with default amount of 1.0
        result = exchange_currency(from_currency, to_currency, 1.0)
        
        # Prepare simplified response with only exchange rate information
        response_data = {
            "status": "success",
            "data": {
                "from_currency": result["from_currency"],
                "to_currency": result["to_currency"],
                "exchange_rate": result["exchange_rate"],
                "base_currency": result["base_currency"],
                "last_update": result["last_update"]
            }
        }
        
        logging.info(f"Successfully processed currency exchange rate: 1 {result['from_currency']} = {result['exchange_rate']:.6f} {result['to_currency']}")
        
        return func.HttpResponse(
            json.dumps(response_data, indent=2),
            status_code=200,
            headers={
                "Content-Type": "application/json"
            }
        )
        
    except ValueError as e:
        # Currency validation or amount validation errors
        error_response = {
            "status": "error",
            "message": str(e),
            "type": "validation_error"
        }
        
        logging.error(f"Validation error in currency exchange: {str(e)}")
        
        return func.HttpResponse(
            json.dumps(error_response, indent=2),
            status_code=400,
            headers={
                "Content-Type": "application/json"
            }
        )
        
    except Exception as e:
        # General errors (database, network, etc.)
        error_response = {
            "status": "error",
            "message": "Failed to process currency exchange",
            "error": str(e),
            "type": "system_error"
        }
        
        logging.error(f"Error processing currency exchange: {str(e)}")
        
        return func.HttpResponse(
            json.dumps(error_response, indent=2),
            status_code=500,
            headers={
                "Content-Type": "application/json"
            }
        )


@app.route(route="supported-currencies", auth_level=func.AuthLevel.FUNCTION, methods=["GET"])
def supported_currencies_http(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP endpoint to get supported currencies information.
    
    GET: /api/supported-currencies
    
    Returns:
        func.HttpResponse: JSON response with supported currencies list
    """
    logging.info('HTTP trigger function processed a supported currencies request')
    
    try:
        # Call the get supported currencies function
        result = get_supported_currencies()
        
        # Prepare success response
        response_data = {
            "status": "success",
            "data": result
        }
        
        logging.info(f"Successfully retrieved supported currencies: {len(result['supported_currencies'])} supported")
        
        return func.HttpResponse(
            json.dumps(response_data, indent=2),
            status_code=200,
            headers={
                "Content-Type": "application/json"
            }
        )
        
    except Exception as e:
        # General errors
        error_response = {
            "status": "error",
            "message": "Failed to retrieve supported currencies",
            "error": str(e)
        }
        
        logging.error(f"Error retrieving supported currencies: {str(e)}")
        
        return func.HttpResponse(
            json.dumps(error_response, indent=2),
            status_code=500,
            headers={
                "Content-Type": "application/json"
            }
        )