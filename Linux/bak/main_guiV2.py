import sys
import os
import subprocess
import shutil
import psutil
import glob
import configparser
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                             QHBoxLayout, QWidget, QFileDialog, QTextEdit, QLabel, 
                             QLineEdit, QProgressBar, QGroupBox, QComboBox, QMessageBox)
from PyQt6.QtCore import Qt, QTimer

class PhotogrammetryApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Van Voorn Photogrammetry Engine - Smart Edition")
        self.resize(1100, 950)

        # Root pad bepaling
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(self.base_dir, "config.ini")
        
        self.init_ui()
        self.load_settings()
        self.refresh_docker_images() # Controleert ook de knop-status
        
        # CPU Monitor Timer
        self.cpu_timer = QTimer()
        self.cpu_timer.timeout.connect(self.update_cpu_usage)
        self.cpu_timer.start(1000)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # --- SECTIE 1: DOCKER ENGINE MANAGEMENT ---
        docker_group = QGroupBox("1. Docker Engine Management")
        docker_layout = QVBoxLayout()
        
        engine_selection_lay = QHBoxLayout()
        self.image_selector = QComboBox()
        btn_refresh_docker = QPushButton("🔄 Ververs")
        btn_refresh_docker.clicked.connect(self.refresh_docker_images)
        
        # De bouw-knop
        self.btn_build_docker = QPushButton("🛠️ Bouw 'vanvoorn-openmvs' Image")
        self.btn_build_docker.setStyleSheet("background-color: #0d47a1; color: white; font-weight: bold;")
        self.btn_build_docker.clicked.connect(self.build_custom_image)
        
        engine_selection_lay.addWidget(QLabel("Selecteer Engine:"))
        engine_selection_lay.addWidget(self.image_selector)
        engine_selection_lay.addWidget(btn_refresh_docker)
        engine_selection_lay.addWidget(self.btn_build_docker)
        
        docker_layout.addLayout(engine_selection_lay)
        docker_group.setLayout(docker_layout)
        layout.addWidget(docker_group)

        # --- SECTIE 2: MESHROOM CONFIG ---
        config_group = QGroupBox("2. Meshroom Systeem Paden")
        config_layout = QVBoxLayout()

        bin_lay = QHBoxLayout()
        self.mesh_bin_input = QLineEdit("/mnt/VG_00/Portable.APPS/Meshroom/Meshroom-2025.1.0/aliceVision/bin")
        btn_bin = QPushButton("Browse Bin")
        btn_bin.clicked.connect(lambda: self.browse_dir(self.mesh_bin_input))
        bin_lay.addWidget(self.mesh_bin_input)
        bin_lay.addWidget(btn_bin)

        lib_lay = QHBoxLayout()
        self.mesh_lib_input = QLineEdit("/mnt/VG_00/Portable.APPS/Meshroom/Meshroom-2025.1.0/aliceVision/lib:/mnt/VG_00/Portable.APPS/Meshroom/Meshroom-2025.1.0/lib")
        btn_lib = QPushButton("Add Lib Path")
        btn_lib.clicked.connect(lambda: self.browse_dir(self.mesh_lib_input, append=True))
        lib_lay.addWidget(self.mesh_lib_input)
        lib_lay.addWidget(btn_lib)

        config_layout.addWidget(QLabel("Pad naar aliceVision/bin:"))
        config_layout.addLayout(bin_lay)
        config_layout.addWidget(QLabel("Pad naar Libraries (LD_LIBRARY_PATH):"))
        config_layout.addLayout(lib_lay)
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # --- SECTIE 3: PROJECT & DATA ---
        project_group = QGroupBox("3. Project & Data Selectie")
        project_layout = QVBoxLayout()

        self.project_name_input = QLineEdit()
        self.project_name_input.setPlaceholderText("Unieke projectnaam...")
        
        cache_lay = QHBoxLayout()
        self.mesh_project_input = QLineEdit()
        self.mesh_project_input.setPlaceholderText("Selecteer de Meshroom Project Map...")
        btn_scan = QPushButton("📁 Scan Project")
        btn_scan.clicked.connect(self.scan_meshroom_project)
        cache_lay.addWidget(self.mesh_project_input)
        cache_lay.addWidget(btn_scan)

        self.sfm_selector = QComboBox()
        
        photo_lay = QHBoxLayout()
        self.photo_input = QLineEdit()
        btn_photo = QPushButton("Browse Foto's")
        btn_photo.clicked.connect(lambda: self.browse_dir(self.photo_input))
        photo_lay.addWidget(self.photo_input)
        photo_lay.addWidget(btn_photo)

        project_layout.addWidget(QLabel("Projectnaam (Output folder):"))
        project_layout.addWidget(self.project_name_input)
        project_layout.addWidget(QLabel("Meshroom Project Locatie (om SfM te vinden):"))
        project_layout.addLayout(cache_lay)
        project_layout.addWidget(QLabel("Geselecteerde SfM data uit cache:"))
        project_layout.addWidget(self.sfm_selector)
        project_layout.addWidget(QLabel("Bron Foto Map (Originelen):"))
        project_layout.addLayout(photo_lay)
        
        project_group.setLayout(project_layout)
        layout.addWidget(project_group)

        # --- SECTIE 4: STATUS & BEDIENING ---
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Klaar voor start.")
        
        cpu_box = QHBoxLayout()
        cpu_box.addWidget(QLabel("CPU Usage:"))
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setFixedWidth(200)
        self.cpu_bar.setTextVisible(True)
        cpu_box.addWidget(self.cpu_bar)
        
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addLayout(cpu_box)
        layout.addLayout(status_layout)

        btn_run_lay = QHBoxLayout()
        self.btn_run = QPushButton("🚀 START VOLLEDIGE PIPELINE")
        self.btn_run.setStyleSheet("background-color: #1b5e20; color: white; font-weight: bold; padding: 15px; font-size: 14px;")
        self.btn_run.clicked.connect(self.run_full_pipeline)
        
        self.btn_stop = QPushButton("🛑 FORCEER STOP")
        self.btn_stop.setStyleSheet("background-color: #b71c1c; color: white; font-weight: bold;")
        self.btn_stop.clicked.connect(self.stop_process)
        
        btn_run_lay.addWidget(self.btn_run)
        btn_run_lay.addWidget(self.btn_stop)
        layout.addLayout(btn_run_lay)

        # Log
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("background-color: #000; color: #00ff00; font-family: 'Monospace'; font-size: 10pt;")
        layout.addWidget(self.log_output)

    # --- DOCKER MANAGEMENT LOGICA ---

    def refresh_docker_images(self):
        self.image_selector.clear()
        image_exists = False
        try:
            result = subprocess.run(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"], 
                                    capture_output=True, text=True)
            images = result.stdout.strip().split('\n')
            for img in images:
                if img.strip():
                    self.image_selector.addItem(img)
                    if img.strip() == "vanvoorn-openmvs:latest":
                        image_exists = True
            
            # De knop verbergen als de image al bestaat
            self.btn_build_docker.setVisible(not image_exists)
            
            idx = self.image_selector.findText("vanvoorn-openmvs:latest")
            if idx != -1: self.image_selector.setCurrentIndex(idx)
        except:
            self.log("[FOUT] Docker is niet bereikbaar.")

    def build_custom_image(self):
        self.log("\n--- BOUWEN CUSTOM DOCKER IMAGE ---")
        dockerfile = (
            "FROM ubuntu:24.04\n"
            "RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y "
            "libopencv-dev libjxl-dev libcgal-dev libceres-dev libsuitesparse-dev "
            "libboost-iostreams-dev libboost-program-options-dev libboost-system-dev "
            "libboost-serialization-dev libboost-python-dev && "
            "rm -rf /var/lib/apt/lists/*"
        )
        temp_df = os.path.join(self.base_dir, "Dockerfile_temp")
        with open(temp_df, "w") as f: f.write(dockerfile)
        
        cmd = "docker build -t vanvoorn-openmvs:latest -f Dockerfile_temp ."
        if self.run_command(cmd) == 0:
            QMessageBox.information(self, "Succes", "De engine 'vanvoorn-openmvs' is nu klaar voor gebruik!")
            self.refresh_docker_images()
        os.remove(temp_df)

    # --- DATA & SETTINGS LOGICA ---

    def scan_meshroom_project(self, silent=False):
        if not silent:
            root_dir = QFileDialog.getExistingDirectory(self, "Selecteer Meshroom Project Map")
            if root_dir: self.mesh_project_input.setText(root_dir)
        
        root_dir = self.mesh_project_input.text()
        if not root_dir: return

        self.sfm_selector.clear()
        pattern = os.path.join(root_dir, "MeshroomCache", "ConvertSfMFormat", "**", "*.sfm")
        files = glob.glob(pattern, recursive=True)
        
        if files:
            files.sort(key=os.path.getmtime, reverse=True)
            for f in files:
                mtime = datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M')
                folder_hash = os.path.basename(os.path.dirname(f))[:8]
                self.sfm_selector.addItem(f"[{mtime}] Hash: {folder_hash}... ({f})", f)
        else:
            self.sfm_selector.addItem("Geen SfM data gevonden.")

    def save_settings(self):
        config = configparser.ConfigParser()
        config['SETTINGS'] = {
            'mesh_bin': self.mesh_bin_input.text(),
            'mesh_lib': self.mesh_lib_input.text(),
            'photo_dir': self.photo_input.text(),
            'project_name': self.project_name_input.text(),
            'mesh_project': self.mesh_project_input.text()
        }
        with open(self.config_file, 'w') as f: config.write(f)

    def load_settings(self):
        if os.path.exists(self.config_file):
            config = configparser.ConfigParser()
            config.read(self.config_file)
            if 'SETTINGS' in config:
                s = config['SETTINGS']
                self.mesh_bin_input.setText(s.get('mesh_bin', ''))
                self.mesh_lib_input.setText(s.get('mesh_lib', ''))
                self.photo_input.setText(s.get('photo_dir', ''))
                self.project_name_input.setText(s.get('project_name', ''))
                self.mesh_project_input.setText(s.get('mesh_project', ''))
                if self.mesh_project_input.text(): self.scan_meshroom_project(silent=True)

    # --- RUNTIME LOGICA ---

    def update_cpu_usage(self):
        usage = psutil.cpu_percent()
        self.cpu_bar.setValue(int(usage))
        color = "#f44336" if usage > 85 else "#4caf50"
        self.cpu_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; }}")

    def browse_dir(self, line_edit, append=False):
        d = QFileDialog.getExistingDirectory(self, "Selecteer Map")
        if d: line_edit.setText(f"{line_edit.text()}:{d}" if append and line_edit.text() else d)

    def log(self, text):
        self.log_output.append(text); self.log_output.ensureCursorVisible()
        QApplication.processEvents()

    def stop_process(self):
        subprocess.run("docker stop $(docker ps -q)", shell=True)
        self.log("\n[!] PROCES GESTOPT")

    def run_command(self, cmd, env=None):
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, text=True)
        for line in process.stdout: self.log(line.strip())
        process.wait()
        return process.returncode

    def run_full_pipeline(self):
        self.save_settings()
        engine = self.image_selector.currentText()
        sfm_file = self.sfm_selector.currentData()
        project_name = self.project_name_input.text().strip()
        photo_dir = self.photo_input.text().strip()

        if not engine or not sfm_file or not project_name:
            QMessageBox.critical(self, "Fout", "Niet alle gegevens zijn ingevuld!")
            return

        work_dir = os.path.join(self.base_dir, "projects", project_name)
        colmap_dir = os.path.join(work_dir, "colmap_data")

        if os.path.exists(work_dir): shutil.rmtree(work_dir)
        os.makedirs(work_dir, exist_ok=True)

        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = self.mesh_lib_input.text()
        env["ALICEVISION_ROOT"] = os.path.dirname(self.mesh_bin_input.text())
        
        self.log(f"--- START PIPELINE: {project_name} ---")

        # 1. Export
        export_cmd = f"'{self.mesh_bin_input.text()}/aliceVision_exportColmap' -i '{sfm_file}' -o '{colmap_dir}'"
        if self.run_command(export_cmd, env) != 0: return

        # 2. Pinhole Patch
        self.log("--- PATCHING PINHOLE ---")
        src_cam = None
        for root, dirs, files in os.walk(colmap_dir):
            if "cameras.txt" in files:
                src_cam = os.path.join(root, "cameras.txt")
                src_images = os.path.join(root, "images.txt")
                src_points = os.path.join(root, "points3D.txt")
                break

        if src_cam:
            dst_sparse = os.path.join(colmap_dir, "sparse")
            os.makedirs(dst_sparse, exist_ok=True)
            with open(src_cam, 'r') as f: lines = f.readlines()
            with open(os.path.join(dst_sparse, "cameras.txt"), 'w') as f:
                for line in lines:
                    if line.startswith("#") or not line.strip(): f.write(line)
                    else:
                        p = line.split()
                        if len(p) >= 8: f.write(f"{p[0]} PINHOLE {p[2]} {p[3]} {p[4]} {p[5]} {p[6]} {p[7]}\n")
            shutil.copy(src_images, os.path.join(dst_sparse, "images.txt"))
            shutil.copy(src_points, os.path.join(dst_sparse, "points3D.txt"))
            os.makedirs(os.path.join(colmap_dir, "images"), exist_ok=True)
            subprocess.run(f"cp '{photo_dir}'/*.JPG '{colmap_dir}/images/' 2>/dev/null", shell=True)
            subprocess.run(f"cp '{photo_dir}'/*.jpg '{colmap_dir}/images/' 2>/dev/null", shell=True)
        else: return

        # 3. Docker Compute
        docker_cmd = (
            f"docker run --rm -v '{self.base_dir}':/pipeline {engine} bash -c '"
            f"cd /pipeline/projects/{project_name} && "
            f"/pipeline/bin/InterfaceCOLMAP -i colmap_data -o model.mvs && "
            f"/pipeline/bin/DensifyPointCloud model.mvs --estimate-roi 0 && "
            f"/pipeline/bin/ReconstructMesh model_dense.mvs && "
            f"/pipeline/bin/TextureMesh model_dense.mvs --mesh-file model_dense_mesh.ply --export-type obj"
            "'"
        )
        if self.run_command(docker_cmd) == 0:
            self.log(f"\n[SUCCES] Project {project_name} voltooid!")

if __name__ == "__main__":
    app = QApplication(sys.argv); window = PhotogrammetryApp(); window.show(); sys.exit(app.exec())
