from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse
import logging
from typing import List, Dict, Any
import io

from services import WordParserService, LLMService, CosmosService
from models import Fund, FundResponseDTO


logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/fund-upload", tags=["Fund Upload"])

# Service instances (you might want to use dependency injection in production)
word_parser = WordParserService()
llm_service = LLMService()
cosmos_service = CosmosService()


@router.post("/process-document")
async def process_fund_document(
    file: UploadFile = File(...),
    user_id: str = None
) -> JSONResponse:
    """
    Process a Word document to extract fund data and store in database
    
    Workflow:
    1. Validate uploaded file
    2. Extract text using WordParserService
    3. Extract structured fund data using LLMService
    4. Store fund data using CosmosService
    
    Args:
        file: Uploaded Word document (.docx)
        user_id: ID of the user uploading the document
        
    Returns:
        JSONResponse with processing results and uploaded fund details
    """
    
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    
    try:
        # Step 1: Validate file
        if not file.filename.lower().endswith('.docx'):
            raise HTTPException(
                status_code=400, 
                detail="Only .docx files are supported"
            )
        
        logger.info(f"Processing document: {file.filename} for user: {user_id}")
        
        # Step 2: Read file content
        file_content = await file.read()
        if not file_content:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        # Step 3: Extract text from Word document
        logger.info("Extracting text from Word document")
        try:
            text_content = word_parser.extract_text_from_word(io.BytesIO(file_content))
            if not text_content.strip():
                raise HTTPException(
                    status_code=400, 
                    detail="No text content found in the document"
                )
            logger.info(f"Extracted {len(text_content)} characters from document")
        except Exception as e:
            logger.error(f"Error extracting text from document: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to extract text from document: {str(e)}"
            )
        
        # Step 4: Extract structured fund data using LLM
        logger.info("Processing text with LLM to extract fund data")
        try:
            funds_data = llm_service.get_funds_data(text_content)
            if not funds_data:
                return JSONResponse(
                    status_code=200,
                    content={
                        "message": "No fund data found in the document",
                        "text_length": len(text_content),
                        "funds_extracted": 0,
                        "upload_results": None
                    }
                )
            logger.info(f"LLM extracted {len(funds_data)} funds from text")
        except Exception as e:
            logger.error(f"Error processing text with LLM: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to process text with LLM: {str(e)}"
            )
        
        # Step 5: Convert to Fund objects and add user_id
        logger.info("Converting extracted data to Fund objects")
        try:
            funds = []
            for fund_data in funds_data:
                # Add user_id to fund data
                fund_data['user_id'] = user_id
                
                # Create Fund object (this validates the data)
                fund = Fund(**fund_data)
                funds.append(fund)
            
            logger.info(f"Successfully created {len(funds)} Fund objects")
        except Exception as e:
            logger.error(f"Error creating Fund objects: {str(e)}")
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid fund data structure: {str(e)}"
            )
        
        # Step 6: Upload funds to Cosmos DB
        logger.info("Uploading funds to Cosmos DB")
        try:
            upload_results = cosmos_service.upload_multiple_funds(funds, user_id)
            logger.info(f"Upload completed: {upload_results['uploaded_count']} uploaded, {upload_results['skipped_count']} skipped, {upload_results['error_count']} errors")
        except Exception as e:
            logger.error(f"Error uploading funds to Cosmos DB: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to upload funds to database: {str(e)}"
            )
        
        # Step 7: Return results
        return JSONResponse(
            status_code=200,
            content={
                "message": "Document processed successfully",
                "filename": file.filename,
                "user_id": user_id,
                "text_length": len(text_content),
                "funds_extracted": len(funds_data),
                "upload_results": upload_results,
                "summary": {
                    "total_funds_found": upload_results["total_funds"],
                    "successfully_uploaded": upload_results["uploaded_count"],
                    "skipped_existing": upload_results["skipped_count"],
                    "errors": upload_results["error_count"]
                }
            }
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle any unexpected errors
        logger.error(f"Unexpected error processing document: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"An unexpected error occurred: {str(e)}"
        )


