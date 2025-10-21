import logging
from typing import Dict, Any, Optional
from applicationinsights import TelemetryClient
from langgraph_pipeline.config import APP_INSIGHTS_CONNECTION_STRING
from opencensus.ext.azure.log_exporter import AzureLogHandler


class ApplicationInsightsClient:
    '''
    Client for Azure Application Insights that provides methods to log custom events.
    '''

    def __init__(self):
        '''
        Initialize the Application Insights client with a connection string.
        '''
        self.connection_string = APP_INSIGHTS_CONNECTION_STRING
        self.is_telemetry_enabled = bool(self.connection_string)
        self._initialize_telemetry_client()
        self._initialize_logger()

    def _initialize_telemetry_client(self) -> None:
        '''Initialize the Application Insights Telemetry Client.'''
        if self.is_telemetry_enabled:
            self.telemetry_client = TelemetryClient(self.connection_string)
            self.telemetry_client.channel.sender.send_interval_in_milliseconds = 5000
        else:
            # Create a dummy telemetry client
            self.telemetry_client = type('DummyTelemetryClient', (), {
                'track_event': lambda *args, **kwargs: None,
                'track_metric': lambda *args, **kwargs: None,
                'track_exception': lambda *args, **kwargs: None,
                'flush': lambda *args, **kwargs: None
            })()
    
    def _initialize_logger(self) -> None:
        '''Initialize the logger with Azure Log Handler for standard logging.'''
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        if self.logger.handlers:
            self.logger.handlers.clear()
            
        if self.is_telemetry_enabled:
            azure_handler = AzureLogHandler(connection_string=self.connection_string)
            self.logger.addHandler(azure_handler)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        self.logger.addHandler(console_handler)
    
    def track_event(self, name: str, properties: Optional[Dict[str, str]] = None, measurements: Optional[Dict[str, float]] = None) -> None:
        '''
        Track a custom event.
        
        Args:
            name: The name of the event
            properties: Optional dictionary of string properties
            measurements: Optional dictionary of numeric measurements
        '''
        self.telemetry_client.track_event(name, properties, measurements)
        
    def track_metric(self, name: str, value: float, properties: Optional[Dict[str, str]] = None) -> None:
        '''
        Track a custom metric.
        
        Args:
            name: The name of the metric
            value: The value of the metric
            properties: Optional dictionary of properties
        '''
        self.telemetry_client.track_metric(name, value, properties=properties)
    
    def log_info(self, message: str, custom_dimensions: Optional[Dict[str, Any]] = None) -> None:
        '''
        Log an informational message.
        
        Args:
            message: The message to log
            custom_dimensions: Optional dictionary of custom dimensions to include
        '''
        if custom_dimensions:
            self.logger.info(message, extra={'custom_dimensions': custom_dimensions})
        else:
            self.logger.info(message)
    
    def log_warning(self, message: str, custom_dimensions: Optional[Dict[str, Any]] = None) -> None:
        '''
        Log a warning message.
        
        Args:
            message: The warning message to log
            custom_dimensions: Optional dictionary of custom dimensions to include
        '''
        if custom_dimensions:
            self.logger.warning(message, extra={'custom_dimensions': custom_dimensions})
        else:
            self.logger.warning(message)
    
    def log_error(self, message: str, custom_dimensions: Optional[Dict[str, Any]] = None) -> None:
        '''
        Log an error message.
        
        Args:
            message: The error message to log
            custom_dimensions: Optional dictionary of custom dimensions to include
        '''
        if custom_dimensions:
            self.logger.error(message, extra={'custom_dimensions': custom_dimensions})
        else:
            self.logger.error(message)
    
    def log_exception(self, exception: Exception, custom_dimensions: Optional[Dict[str, Any]] = None) -> None:
        '''
        Log an exception.
        
        Args:
            exception: The exception to log
            custom_dimensions: Optional dictionary of custom dimensions to include
        '''
        self.telemetry_client.track_exception(exception, properties=custom_dimensions)
        if custom_dimensions:
            self.logger.exception(exception, extra={'custom_dimensions': custom_dimensions})
        else:
            self.logger.exception(exception)
    
    def flush(self) -> None:
        '''
        Flush all telemetry in the buffer.
        Call this method before your application exits to ensure all telemetry is sent.
        '''
        self.telemetry_client.flush()


telemetry_client = ApplicationInsightsClient()