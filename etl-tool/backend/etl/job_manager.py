import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import threading
from etl.extractor import Extractor
from etl.transformer import Transformer
from etl.loader import Loader


class JobManager:
    """Manages ETL jobs"""
    
    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
    
    def create_job(
        self,
        name: str,
        source_type: str,
        source_config: Dict[str, Any],
        destination_type: str,
        destination_config: Dict[str, Any],
        transformations: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Create a new ETL job"""
        job_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        job = {
            "job_id": job_id,
            "name": name,
            "source_type": source_type,
            "source_config": source_config,
            "destination_type": destination_type,
            "destination_config": destination_config,
            "transformations": transformations or [],
            "status": "pending",
            "progress": 0.0,
            "created_at": now,
            "updated_at": now,
            "error": None
        }
        
        self.jobs[job_id] = job
        return job
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by ID"""
        return self.jobs.get(job_id)
    
    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Get all jobs"""
        return list(self.jobs.values())
    
    def delete_job(self, job_id: str) -> bool:
        """Delete a job"""
        if job_id in self.jobs:
            del self.jobs[job_id]
            return True
        return False
    
    def run_job(self, job_id: str) -> None:
        """Run an ETL job in a separate thread"""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        if job["status"] == "running":
            raise ValueError(f"Job {job_id} is already running")
        
        # Start job in a separate thread
        thread = threading.Thread(target=self._execute_job, args=(job_id,))
        thread.daemon = True
        thread.start()
    
    def _execute_job(self, job_id: str) -> None:
        """Execute an ETL job"""
        job = self.jobs[job_id]
        
        try:
            # Update status
            self._update_job_status(job_id, "running", 10.0)
            
            # Extract
            df = Extractor.extract(job["source_type"], job["source_config"])
            self._update_job_status(job_id, "running", 40.0)
            
            # Transform
            if job["transformations"]:
                df = Transformer.transform(df, job["transformations"])
            self._update_job_status(job_id, "running", 70.0)
            
            # Load
            Loader.load(df, job["destination_type"], job["destination_config"])
            self._update_job_status(job_id, "completed", 100.0)
            
        except Exception as e:
            self._update_job_status(job_id, "failed", job.get("progress", 0.0), str(e))
    
    def _update_job_status(
        self,
        job_id: str,
        status: str,
        progress: float,
        error: Optional[str] = None
    ) -> None:
        """Update job status"""
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = status
            self.jobs[job_id]["progress"] = progress
            self.jobs[job_id]["updated_at"] = datetime.now().isoformat()
            if error:
                self.jobs[job_id]["error"] = error

