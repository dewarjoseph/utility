"""
Automated Santa Cruz County GIS Data Bulk Downloader
Uses DCAT-US 1.1 feed to download all 162 available layers.
"""

import requests
import json
import os
from pathlib import Path
from typing import List, Dict
import time
from urllib.parse import urlparse

class SantaCruzDataDownloader:
    """
    Automated bulk downloader for Santa Cruz County Open Data.
    """
    
    def __init__(self, cache_dir="gis_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # DCAT-US 1.1 catalog feed
        self.catalog_url = "https://opendata-sccgis.opendata.arcgis.com/api/feed/dcat-us/1.1.json"
        
        # Download statistics
        self.stats = {
            "total_datasets": 0,
            "downloaded": 0,
            "skipped": 0,
            "failed": 0
        }
        
        # Priority categories (download these first)
        self.priority_keywords = [
            "parcel", "zoning", "lidar", "dtm", "dem", "elevation",
            "flood", "fire", "hazard", "utility", "infrastructure"
        ]
    
    def fetch_catalog(self) -> Dict:
        """
        Fetch the DCAT-US 1.1 catalog containing all datasets.
        """
        print("[Catalog] Fetching Santa Cruz County data catalog...")
        
        try:
            response = requests.get(self.catalog_url, timeout=30)
            response.raise_for_status()
            catalog = response.json()
            
            self.stats["total_datasets"] = len(catalog.get("dataset", []))
            print(f"[Catalog] OK Found {self.stats['total_datasets']} datasets")
            
            return catalog
        except Exception as e:
            print(f"[Catalog] ERROR Failed to fetch catalog: {e}")
            return {}
    
    def parse_dataset(self, dataset: Dict) -> Dict:
        """
        Extract download URLs and metadata from a dataset entry.
        """
        info = {
            "title": dataset.get("title", "Unknown"),
            "description": dataset.get("description", ""),
            "keywords": dataset.get("keyword", []),
            "modified": dataset.get("modified", ""),
            "downloads": []
        }
        
        # Extract download URLs from distribution array
        distributions = dataset.get("distribution", [])
        for dist in distributions:
            format_type = dist.get("format", "").upper()
            download_url = dist.get("downloadURL") or dist.get("accessURL")
            
            if download_url and format_type in ["SHAPEFILE", "GEOTIFF", "TIF", "ZIP", "CSV"]:
                info["downloads"].append({
                    "format": format_type,
                    "url": download_url
                })
        
        return info
    
    def is_priority_dataset(self, dataset_info: Dict) -> bool:
        """
        Check if dataset matches priority keywords.
        """
        text = (dataset_info["title"] + " " + " ".join(dataset_info["keywords"])).lower()
        return any(keyword in text for keyword in self.priority_keywords)
    
    def download_file(self, url: str, output_path: Path) -> bool:
        """
        Download a file with progress indication.
        """
        try:
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            with open(output_path, 'wb') as f:
                if total_size == 0:
                    f.write(response.content)
                else:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        # Simple progress indicator
                        progress = (downloaded / total_size) * 100
                        if downloaded % (total_size // 10 + 1) == 0:
                            print(f"   [{progress:.0f}%]", end='\r')
            
            print(f"   [100%] OK Downloaded {output_path.name}")
            return True
            
        except Exception as e:
            print(f"   ERROR Download failed: {e}")
            return False
    
    def download_dataset(self, dataset_info: Dict, category: str = "general") -> bool:
        """
        Download all files for a dataset.
        """
        if not dataset_info["downloads"]:
            print(f"[Skip] {dataset_info['title']} - No downloadable files")
            self.stats["skipped"] += 1
            return False
        
        # Create category subdirectory
        category_dir = self.cache_dir / category
        category_dir.mkdir(exist_ok=True)
        
        # Sanitize title for filename
        safe_title = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' 
                            for c in dataset_info['title'])
        safe_title = safe_title.replace(' ', '_')[:50]  # Limit length
        
        success = False
        for download in dataset_info["downloads"]:
            url = download["url"]
            ext = download["format"].lower()
            if ext == "shapefile":
                ext = "zip"
            
            output_path = category_dir / f"{safe_title}.{ext}"
            
            # Skip if already downloaded
            if output_path.exists():
                print(f"[Skip] {dataset_info['title']} - Already exists")
                self.stats["skipped"] += 1
                return True
            
            print(f"[Download] {dataset_info['title']} ({download['format']})")
            
            if self.download_file(url, output_path):
                success = True
                self.stats["downloaded"] += 1
            else:
                self.stats["failed"] += 1
        
        return success
    
    def download_all(self, priority_only=False, limit=None):
        """
        Download all datasets from the catalog.
        
        Args:
            priority_only: Only download priority datasets
            limit: Maximum number of datasets to download (for testing)
        """
        catalog = self.fetch_catalog()
        
        if not catalog:
            print("[Error] Could not fetch catalog")
            return
        
        datasets = catalog.get("dataset", [])
        
        # Parse all datasets
        parsed_datasets = []
        for dataset in datasets:
            info = self.parse_dataset(dataset)
            if info["downloads"]:  # Only include datasets with download links
                parsed_datasets.append(info)
        
        # Sort: priority first, then alphabetically
        parsed_datasets.sort(
            key=lambda x: (not self.is_priority_dataset(x), x["title"])
        )
        
        # Filter if priority_only
        if priority_only:
            parsed_datasets = [d for d in parsed_datasets if self.is_priority_dataset(d)]
            print(f"\n[Mode] Priority-only: {len(parsed_datasets)} datasets")
        
        # Apply limit
        if limit:
            parsed_datasets = parsed_datasets[:limit]
            print(f"[Mode] Limited to {limit} datasets")
        
        print(f"\n{'='*60}")
        print(f"Starting download of {len(parsed_datasets)} datasets")
        print(f"{'='*60}\n")
        
        # Download each dataset
        for i, dataset_info in enumerate(parsed_datasets, 1):
            print(f"\n[{i}/{len(parsed_datasets)}] Processing...")
            
            # Categorize
            if self.is_priority_dataset(dataset_info):
                category = "priority"
            else:
                category = "general"
            
            self.download_dataset(dataset_info, category)
            
            # Rate limiting - be respectful to the server
            time.sleep(1)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"DOWNLOAD COMPLETE")
        print(f"{'='*60}")
        print(f"Total datasets in catalog: {self.stats['total_datasets']}")
        print(f"Downloaded: {self.stats['downloaded']}")
        print(f"Skipped (already exists): {self.stats['skipped']}")
        print(f"Failed: {self.stats['failed']}")
        print(f"\nFiles saved to: {self.cache_dir.absolute()}")
    
    def list_available_datasets(self):
        """
        List all available datasets without downloading.
        """
        catalog = self.fetch_catalog()
        
        if not catalog:
            return
        
        datasets = catalog.get("dataset", [])
        
        print(f"\n{'='*60}")
        print(f"AVAILABLE DATASETS ({len(datasets)} total)")
        print(f"{'='*60}\n")
        
        for i, dataset in enumerate(datasets, 1):
            info = self.parse_dataset(dataset)
            priority = "*" if self.is_priority_dataset(info) else " "
            formats = ", ".join(set(d["format"] for d in info["downloads"]))
            
            print(f"{priority} {i:3d}. {info['title']}")
            if formats:
                print(f"       Formats: {formats}")
            print()

def main():
    """CLI interface for the downloader."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Santa Cruz County GIS Data Bulk Downloader")
    parser.add_argument("--list", action="store_true", help="List available datasets without downloading")
    parser.add_argument("--priority-only", action="store_true", help="Download only priority datasets")
    parser.add_argument("--limit", type=int, help="Limit number of downloads (for testing)")
    parser.add_argument("--cache-dir", default="gis_cache", help="Directory to save files")
    
    args = parser.parse_args()
    
    downloader = SantaCruzDataDownloader(cache_dir=args.cache_dir)
    
    if args.list:
        downloader.list_available_datasets()
    else:
        downloader.download_all(priority_only=args.priority_only, limit=args.limit)

if __name__ == "__main__":
    main()
