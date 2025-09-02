#!/usr/bin/env python3
"""
Simple PCD Viewer using Open3D
Install with: pip install open3d
"""

import sys
import os
import argparse
from pathlib import Path

def view_pcd_with_open3d(pcd_file):
    """View a PCD file using Open3D."""
    try:
        import open3d as o3d
        print(f"Loading PCD file: {pcd_file}")
        
        # Load the point cloud
        pcd = o3d.io.read_point_cloud(pcd_file)
        
        if len(pcd.points) == 0:
            print("Error: No points found in PCD file")
            return
        
        print(f"Point cloud loaded: {len(pcd.points)} points")
        print("Controls:")
        print("  - Mouse: Rotate, zoom, pan")
        print("  - Q: Exit viewer")
        
        # Visualize
        o3d.visualization.draw_geometries([pcd])
        
    except ImportError:
        print("Open3D not installed. Install with: pip install open3d")
        print("Alternative: Use CloudCompare (https://www.danielgm.net/cc/)")
    except Exception as e:
        print(f"Error loading PCD file: {e}")

def view_pcd_with_pyvista(pcd_file):
    """View a PCD file using PyVista."""
    try:
        import pyvista as pv
        import pypcd
        import numpy as np
        
        print(f"Loading PCD file: {pcd_file}")
        
        # Load using pypcd
        pc = pypcd.PointCloud.from_path(pcd_file)
        
        # Convert to PyVista format
        points = np.column_stack([pc.pc_data['x'], pc.pc_data['y'], pc.pc_data['z']])
        cloud = pv.PolyData(points)
        
        print(f"Point cloud loaded: {len(points)} points")
        print("Controls:")
        print("  - Mouse: Rotate, zoom, pan")
        print("  - Q: Exit viewer")
        
        # Visualize
        plotter = pv.Plotter()
        plotter.add_points(cloud, point_size=2, color='white')
        plotter.show()
        
    except ImportError as e:
        print(f"Required libraries not installed: {e}")
        print("Install with: pip install pyvista pypcd")
    except Exception as e:
        print(f"Error loading PCD file: {e}")

def list_pcd_files(directory):
    """List all PCD files in a directory."""
    pcd_files = list(Path(directory).glob("*.pcd"))
    
    if not pcd_files:
        print(f"No PCD files found in {directory}")
        return []
    
    print(f"Found {len(pcd_files)} PCD files in {directory}:")
    for i, file in enumerate(pcd_files):
        size_mb = file.stat().st_size / (1024 * 1024)
        print(f"  {i+1:2d}. {file.name} ({size_mb:.1f} MB)")
    
    return pcd_files

def main():
    parser = argparse.ArgumentParser(description="Simple PCD Viewer")
    parser.add_argument("pcd_file", nargs="?", help="PCD file to view")
    parser.add_argument("--list", action="store_true", help="List PCD files in current directory")
    parser.add_argument("--viewer", choices=["open3d", "pyvista"], default="open3d", 
                       help="Viewer to use (default: open3d)")
    
    args = parser.parse_args()
    
    if args.list:
        list_pcd_files(".")
        return
    
    if not args.pcd_file:
        # Look for PCD files in current directory
        pcd_files = list_pcd_files(".")
        if not pcd_files:
            return
        
        # Ask user to select a file
        try:
            choice = input(f"\nSelect file (1-{len(pcd_files)}) or press Enter for first file: ").strip()
            if choice == "":
                choice = 1
            else:
                choice = int(choice)
            
            if 1 <= choice <= len(pcd_files):
                pcd_file = str(pcd_files[choice - 1])
            else:
                print("Invalid choice")
                return
        except (ValueError, KeyboardInterrupt):
            return
    else:
        pcd_file = args.pcd_file
    
    if not os.path.exists(pcd_file):
        print(f"File not found: {pcd_file}")
        return
    
    # View the PCD file
    if args.viewer == "open3d":
        view_pcd_with_open3d(pcd_file)
    else:
        view_pcd_with_pyvista(pcd_file)

if __name__ == "__main__":
    main()
