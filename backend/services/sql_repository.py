from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, Date, text
from sqlalchemy.engine.url import URL
from sqlalchemy.exc import SQLAlchemyError
import logging
from typing import List, Optional, Dict, Any
from datetime import date

from config import (
    SQL_SERVER_USERNAME,
    SQL_SERVER_NAME,
    SQL_SERVER_PASSWORD,
    SQL_SERVER_DATABASE
)
from models.fund import Fund
from services.telemetry_client import telemetry_client

logger = logging.getLogger(__name__)


class SQLRepository:
    """Service for managing SQL Server fund data operations with user isolation"""
    
    def __init__(self):
        """Initialize SQL Server connection and ensure tables exist"""
        try:
            self.db_config = {
                "drivername": "mssql+pyodbc",
                "username": SQL_SERVER_USERNAME,
                "password": SQL_SERVER_PASSWORD,
                "host": SQL_SERVER_NAME,
                "port": 1433,
                "database": SQL_SERVER_DATABASE,
                "query": {"driver": "ODBC Driver 17 for SQL Server"},
            }
            
            self.db_url = URL.create(**self.db_config)
            self.engine = create_engine(self.db_url)
            self.metadata = MetaData()
            
            # Define fundinfo table structure
            self.fundinfo_table = Table(
                'fundinfo',
                self.metadata,
                Column('FundID', Integer, primary_key=True, autoincrement=True),
                Column('UserID', String(255), nullable=False),
                Column('FundName', String(500), nullable=False),
                Column('Vintage', Integer, nullable=False),
                Column('Commitment', Integer, nullable=False),
                Column('PaidIn', Integer, nullable=False),
                Column('NAV', Integer, nullable=False),
                Column('NetIRR', Float, nullable=False),
                Column('DPI', Float, nullable=False),
                Column('TVPI', Float, nullable=False),
                Column('PMEvsIndex', Float, nullable=False),
                Column('Unfunded', Integer, nullable=False),
                Column('Status', String(50), nullable=False),
                Column('LastReported', Date, nullable=False),
                extend_existing=True
            )
            
            # Ensure table exists
            self._ensure_table_exists()
            
            telemetry_client.log_info('SQLRepository initialized successfully')
            
        except Exception as e:
            telemetry_client.log_exception(e, {"error": "Failed to initialize SQLRepository"})
            raise
    
    def _ensure_table_exists(self):
        """Ensure fundinfo table exists, create if it doesn't"""
        try:
            with self.engine.connect() as conn:
                # Check if table exists
                result = conn.execute(text(
                    "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_NAME = 'fundinfo'"
                ))
                exists = result.scalar() > 0
                
                if not exists:
                    # Create table
                    self.metadata.create_all(self.engine, tables=[self.fundinfo_table])
                    logger.info("Created fundinfo table")
                    
                    # Create index on UserID and FundName for faster queries
                    conn.execute(text(
                        "CREATE INDEX IX_fundinfo_UserID_FundName "
                        "ON fundinfo(UserID, FundName)"
                    ))
                    conn.commit()
                    logger.info("Created index on UserID and FundName")
                else:
                    logger.info("fundinfo table already exists")
                    
        except Exception as e:
            logger.error(f"Error ensuring table exists: {str(e)}")
            raise
    
    def insert_fund(self, fund: Fund) -> Optional[int]:
        """
        Insert a single fund record into SQL database
        
        Args:
            fund: Fund object to insert
            
        Returns:
            Optional[int]: Inserted FundID or None if failed
        """
        try:
            with self.engine.connect() as conn:
                # Check if fund already exists for this user and last_reported date
                check_query = text(
                    "SELECT FundID FROM fundinfo "
                    "WHERE UserID = :user_id AND FundName = :fund_name "
                    "AND LastReported = :last_reported"
                )
                result = conn.execute(
                    check_query,
                    {
                        "user_id": fund.user_id,
                        "fund_name": fund.fund_name,
                        "last_reported": fund.last_reported
                    }
                )
                existing = result.fetchone()
                
                if existing:
                    logger.info(f"Fund already exists: {fund.fund_name} for user {fund.user_id}")
                    return existing[0]
                
                # Insert new fund using OUTPUT clause for reliable ID retrieval
                insert_query = text(
                    "INSERT INTO fundinfo "
                    "(UserID, FundName, Vintage, Commitment, PaidIn, NAV, NetIRR, "
                    "DPI, TVPI, PMEvsIndex, Unfunded, Status, LastReported) "
                    "OUTPUT INSERTED.FundID "
                    "VALUES "
                    "(:user_id, :fund_name, :vintage, :commitment, :paid_in, :nav, "
                    ":net_irr, :dpi, :tvpi, :pme_vs_index, :unfunded, :status, :last_reported)"
                )
                
                result = conn.execute(
                    insert_query,
                    {
                        "user_id": fund.user_id,
                        "fund_name": fund.fund_name,
                        "vintage": fund.vintage,
                        "commitment": fund.commitment,
                        "paid_in": fund.paid_in,
                        "nav": fund.nav,
                        "net_irr": fund.net_irr,
                        "dpi": fund.dpi,
                        "tvpi": fund.tvpi,
                        "pme_vs_index": fund.pme_vs_index,
                        "unfunded": fund.unfunded,
                        "status": fund.status,
                        "last_reported": fund.last_reported
                    }
                )
                
                # Get the inserted ID from OUTPUT clause
                fund_id_row = result.fetchone()
                if fund_id_row is None:
                    logger.error(f"Failed to insert fund {fund.fund_name} - no ID returned")
                    return None
                
                fund_id = fund_id_row[0]
                conn.commit()
                
                logger.info(f"Inserted fund {fund.fund_name} with FundID {fund_id}")
                return fund_id
                
        except SQLAlchemyError as e:
            logger.error(f"Error inserting fund {fund.fund_name}: {str(e)}")
            return None
    
    def insert_multiple_funds(self, funds: List[Fund]) -> Dict[str, Any]:
        """
        Insert multiple fund records into SQL database
        
        Args:
            funds: List of Fund objects to insert
            
        Returns:
            Dict with insertion results
        """
        results = {
            "total": len(funds),
            "inserted": 0,
            "skipped": 0,
            "errors": 0,
            "fund_ids": []
        }
        
        for fund in funds:
            fund_id = self.insert_fund(fund)
            if fund_id:
                results["inserted"] += 1
                results["fund_ids"].append(fund_id)
            else:
                results["errors"] += 1
        
        logger.info(
            f"Batch insert complete: {results['inserted']} inserted, "
            f"{results['errors']} errors out of {results['total']} total"
        )
        
        return results
    
    def get_user_funds(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all funds for a specific user
        
        Args:
            user_id: ID of the user
            
        Returns:
            List of fund records
        """
        try:
            with self.engine.connect() as conn:
                query = text(
                    "SELECT * FROM fundinfo WHERE UserID = :user_id "
                    "ORDER BY LastReported DESC, FundName"
                )
                result = conn.execute(query, {"user_id": user_id})
                
                funds = []
                for row in result:
                    funds.append(dict(row._mapping))
                
                logger.info(f"Retrieved {len(funds)} funds for user {user_id}")
                return funds
                
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving funds for user {user_id}: {str(e)}")
            return []
    
    def get_user_latest_funds(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get the latest fund data for each fund name for a specific user
        
        Args:
            user_id: ID of the user
            
        Returns:
            List of latest fund records
        """
        try:
            with self.engine.connect() as conn:
                query = text("""
                    SELECT f.*
                    FROM fundinfo f
                    INNER JOIN (
                        SELECT FundName, MAX(LastReported) as MaxDate
                        FROM fundinfo
                        WHERE UserID = :user_id
                        GROUP BY FundName
                    ) latest ON f.FundName = latest.FundName 
                        AND f.LastReported = latest.MaxDate
                    WHERE f.UserID = :user_id
                    ORDER BY f.FundName
                """)
                result = conn.execute(query, {"user_id": user_id})
                
                funds = []
                for row in result:
                    funds.append(dict(row._mapping))
                
                logger.info(f"Retrieved {len(funds)} latest funds for user {user_id}")
                return funds
                
        except SQLAlchemyError as e:
            logger.error(f"Error retrieving latest funds for user {user_id}: {str(e)}")
            return []
    
    def delete_user_funds(self, user_id: str, fund_name: Optional[str] = None) -> int:
        """
        Delete funds for a user (optionally for a specific fund name)
        
        Args:
            user_id: ID of the user
            fund_name: Optional fund name to delete specific fund
            
        Returns:
            Number of records deleted
        """
        try:
            with self.engine.connect() as conn:
                if fund_name:
                    query = text(
                        "DELETE FROM fundinfo "
                        "WHERE UserID = :user_id AND FundName = :fund_name"
                    )
                    result = conn.execute(
                        query,
                        {"user_id": user_id, "fund_name": fund_name}
                    )
                else:
                    query = text("DELETE FROM fundinfo WHERE UserID = :user_id")
                    result = conn.execute(query, {"user_id": user_id})
                
                conn.commit()
                deleted = result.rowcount
                logger.info(f"Deleted {deleted} records for user {user_id}")
                return deleted
                
        except SQLAlchemyError as e:
            logger.error(f"Error deleting funds for user {user_id}: {str(e)}")
            return 0


# Singleton instance
sql_repository = SQLRepository()
