import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from autonomous_media.db.models import Job, Clip, ClipCandidate, Transcript, SourceVideo, SourcePost, SystemEvent, InventoryItem
from autonomous_media.config import settings

def main():
    print("====================================================")
    print(" YTAuto Pipeline Reset Utility")
    print("====================================================\n")
    
    confirm = input("This will delete all jobs, clips, candidates, transcripts, source posts, and source videos.\nAre you sure you want to proceed? (y/N): ").strip().lower()
    if confirm != 'y':
        print("Reset aborted.")
        sys.exit(0)

    try:
        engine = create_engine(settings.database_url)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()

        print("\nDeleting rows...")
        
        # Deleting in foreign key dependency order
        deleted_events = session.query(SystemEvent).delete()
        print(f"Deleted {deleted_events} system events.")

        deleted_inventory = session.query(InventoryItem).delete()
        print(f"Deleted {deleted_inventory} inventory items.")

        deleted_clips = session.query(Clip).delete()
        print(f"Deleted {deleted_clips} clips.")

        deleted_candidates = session.query(ClipCandidate).delete()
        print(f"Deleted {deleted_candidates} clip candidates.")

        deleted_transcripts = session.query(Transcript).delete()
        print(f"Deleted {deleted_transcripts} transcripts.")

        deleted_videos = session.query(SourceVideo).delete()
        print(f"Deleted {deleted_videos} source videos.")

        deleted_posts = session.query(SourcePost).delete()
        print(f"Deleted {deleted_posts} source posts.")

        deleted_jobs = session.query(Job).delete()
        print(f"Deleted {deleted_jobs} jobs.")

        session.commit()
        print("\nPipeline reset completed successfully! All queues and processed assets are cleared.")
        print("Ready to start afresh.")

    except Exception as e:
        print(f"\nError resetting pipeline: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
