"""Seed sample data for demo/testing purposes."""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.db.session import engine, Base, SessionLocal
from app.models import User, SOP, Log, SOPChunk, LogChunk, ComplianceResult
from app.utils.security import hash_password
from app.services.embeddings import embed_text
from app.services.chunking import chunk_text
from app.services.faiss_store import add_vector

# Sample SOP content
SAMPLE_SOPS = [
    {
        "title": "SOP-001: Equipment Cleaning Procedure",
        "content": """
        STANDARD OPERATING PROCEDURE
        Equipment Cleaning and Sanitization
        
        1. PURPOSE
        To establish a procedure for cleaning and sanitizing manufacturing equipment to prevent cross-contamination.
        
        2. SCOPE
        This procedure applies to all production equipment in the manufacturing area.
        
        3. RESPONSIBILITIES
        3.1 Production Operator: Execute cleaning procedure
        3.2 Supervisor: Verify completion
        3.3 QA: Approve cleaning records
        
        4. PROCEDURE
        4.1 Pre-cleaning Inspection
            - Verify equipment is stopped and locked out
            - Remove all product residue
            - Document initial condition
        
        4.2 Cleaning Steps
            - Apply approved cleaning solution
            - Scrub all contact surfaces for minimum 5 minutes
            - Rinse with purified water
            - Inspect for visual cleanliness
            - Allow to air dry or wipe with lint-free cloth
        
        4.3 Sanitization
            - Apply 70% IPA or approved sanitizer
            - Allow 10 minutes contact time
            - Do not rinse
        
        4.4 Documentation
            - Complete cleaning log
            - Record batch number of cleaning agents
            - Note any deviations
        
        5. FREQUENCY
            - After each batch changeover
            - At end of each shift
            - After maintenance activities
        
        6. ACCEPTANCE CRITERIA
            - No visible residue
            - pH of final rinse within specification
            - Microbial counts within limits
        """
    },
    {
        "title": "SOP-002: Raw Material Verification",
        "content": """
        STANDARD OPERATING PROCEDURE
        Raw Material Receipt and Verification
        
        1. PURPOSE
        To ensure all incoming raw materials meet specifications before use in production.
        
        2. SCOPE
        All raw materials, excipients, and packaging materials.
        
        3. RESPONSIBILITIES
        3.1 Warehouse: Receive and quarantine materials
        3.2 QC: Sample and test materials
        3.3 QA: Review and approve/reject
        
        4. PROCEDURE
        4.1 Receipt
            - Verify supplier COA matches purchase order
            - Check container integrity
            - Apply quarantine label
            - Assign internal batch number
        
        4.2 Sampling
            - Use approved sampling plan
            - Collect representative samples
            - Maintain chain of custody
        
        4.3 Testing
            - Perform identity testing
            - Test against specifications
            - Document all results
        
        4.4 Disposition
            - QA reviews all data
            - Approve for use or reject
            - Update inventory status
        
        5. DOCUMENTATION
            - Material receipt log
            - COA verification record
            - Test results
            - Disposition record
        """
    },
]

# Sample Log content
SAMPLE_LOGS = [
    {
        "title": "Batch Log - BL-2024-001",
        "content": """
        BATCH PRODUCTION LOG
        Batch Number: BL-2024-001
        Product: Pharma Product X
        Date: 2024-01-15
        
        === SHIFT 1 ===
        
        08:00 - Equipment Setup
        - Verified equipment clean status (CLEAN-001)
        - Calibrated scales (CAL-2024-015)
        - Operator: John Smith
        
        08:30 - Material Dispensing
        - Dispensed Raw Material A (Batch: RM-A-2024-005)
        - Weight: 50.0 kg
        - Verified by: Jane Doe
        
        09:00 - Mixing Operation
        - Started mixer at 500 RPM
        - Mixed for 30 minutes
        - Temperature: 25°C
        
        09:30 - Quality Check
        - In-process sample collected
        - pH: 7.2 (Spec: 7.0-7.5)
        - Appearance: Clear solution
        
        10:00 - Filtration
        - Passed through 0.45 micron filter
        - Filter integrity test: PASSED
        - Filtrate volume: 48.5 L
        
        11:00 - End of Shift
        - Equipment cleaned per SOP-001
        - Area sanitized
        - Log completed by: John Smith
        """
    },
    {
        "title": "Batch Log - BL-2024-002",
        "content": """
        BATCH PRODUCTION LOG
        Batch Number: BL-2024-002
        Product: Pharma Product Y
        Date: 2024-01-16
        
        === SHIFT 1 ===
        
        08:00 - Equipment Setup
        - Verified equipment clean status
        - Line clearance completed
        - Operator: Sarah Johnson
        
        08:30 - Material Verification
        - Raw Material B received (Batch: RM-B-2024-003)
        - COA verified
        - Quarantine released by QA
        
        09:00 - Processing
        - Started heating to 60°C
        - Added Material B slowly
        - Stirring rate: 300 RPM
        
        10:00 - Quality Issue
        - Observed slight discoloration
        - Supervisor notified
        - QA consulted
        
        10:30 - Corrective Action
        - Extended mixing time
        - Additional filtration step added
        - Documented deviation DEV-2024-005
        
        11:30 - Completion
        - Final product collected
        - Yield: 95%
        - Sent to packaging
        """
    },
]


def seed_database():
    """Seed the database with sample data."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Create demo user
        print("Creating demo user...")
        demo_user = User(
            name="Demo User",
            email="demo@pharma.com",
            password_hash=hash_password("demo1234"),
        )
        db.add(demo_user)
        db.commit()
        db.refresh(demo_user)
        print(f"  Created user: {demo_user.email}")
        
        # Create SOPs
        print("\nCreating SOPs...")
        for sop_data in SAMPLE_SOPS:
            embedding = embed_text(sop_data["content"])
            sop = SOP(
                title=sop_data["title"],
                content=sop_data["content"],
                embedding_vector=embedding,
            )
            db.add(sop)
            db.commit()
            db.refresh(sop)
            
            # Add to FAISS
            add_vector("sop", embedding, sop.id)
            
            # Create chunks
            chunks = chunk_text(sop_data["content"])
            for idx, chunk in enumerate(chunks):
                chunk_emb = embed_text(chunk)
                sop_chunk = SOPChunk(
                    sop_id=sop.id,
                    chunk_index=idx,
                    content=chunk,
                    embedding_vector=chunk_emb,
                )
                db.add(sop_chunk)
                add_vector("sop_chunk", chunk_emb, sop_chunk.id)
            
            db.commit()
            print(f"  Created SOP: {sop.title} ({len(chunks)} chunks)")
        
        # Create Logs
        print("\nCreating Logs...")
        for log_data in SAMPLE_LOGS:
            embedding = embed_text(log_data["content"])
            log = Log(
                title=log_data["title"],
                content=log_data["content"],
                embedding_vector=embedding,
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            
            # Add to FAISS
            add_vector("log", embedding, log.id)
            
            # Create chunks
            chunks = chunk_text(log_data["content"])
            for idx, chunk in enumerate(chunks):
                chunk_emb = embed_text(chunk)
                log_chunk = LogChunk(
                    log_id=log.id,
                    chunk_index=idx,
                    content=chunk,
                    embedding_vector=chunk_emb,
                )
                db.add(log_chunk)
                add_vector("log_chunk", chunk_emb, log_chunk.id)
            
            db.commit()
            print(f"  Created Log: {log.title} ({len(chunks)} chunks)")
        
        print("\n✅ Database seeded successfully!")
        print("\nDemo Credentials:")
        print("  Email: demo@pharma.com")
        print("  Password: demo1234")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
