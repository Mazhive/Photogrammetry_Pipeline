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
        self.setWindowTitle("Van Voorn Photogrammetry Engine - Smart Guard Edition")
        self.resize(1100, 950)

        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(self.base_dir, "config.ini")
        
        self.init_ui()
        self.load_settings()
        self.refresh_docker_images()
        
        self.cpu_timer = QTimer()
        self.cpu_timer.timeout.connect(self.update_cpu_usage)
        self.cpu_timer.start(1000)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # --- 1. DOCKER ENGINE MANAGEMENT ---
        docker_group = QGroupBox("1. Docker Engine Management")
        docker_layout = QVBoxLayout()
        engine_selection_lay = QHBoxLayout()
        self.image_selector = QComboBox()
        self.image_selector.currentTextChanged.connect(self.validate_selected_image)
        self.validation_label = QLabel("-")
        btn_refresh_docker = QPushButton("🔄 Ververs")
        btn_refresh_docker.clicked.connect(self.refresh_docker_images)
        self.btn_build_docker = QPushButton("🛠️ Bouw Engine")
        self.btn_build_docker.setStyleSheet("background-color: #0d47a1; color: white; font-weight: bold;")
        self.btn_build_docker.clicked.connect(self.build_custom_image)
        engine_selection_lay.addWidget(QLabel("Engine:"))
        engine_selection_lay.addWidget(self.image_selector)
        engine_selection_lay.addWidget(self.validation_label)
        engine_selection_lay.addWidget(btn_refresh_docker)
        engine_selection_lay.addWidget(self.btn_build_docker)
        docker_layout.addLayout(engine_selection_lay)
        docker_group.setLayout(docker_layout)
        layout.addWidget(docker_group)

        # --- 2. MESHROOM & PROJECT ---
        project_group = QGroupBox("2. Meshroom & Project")
        project_layout = QVBoxLayout()
        
        # Bin & Lib met Browse
        for label, attr, default in [("Bin Pad:", "mesh_bin_input", "/mnt/VG_00/Portable.APPS/Meshroom/Meshroom-2025.1.0/aliceVision/bin"), 
                                     ("Lib Pad:", "mesh_lib_input", "/mnt/VG_00/Portable.APPS/Meshroom/Meshroom-2025.1.0/aliceVision/lib:/mnt/VG_00/Portable.APPS/Meshroom/Meshroom-2025.1.0/lib")]:
            project_layout.addWidget(QLabel(label))
            lay = QHBoxLayout()
            edit = QLineEdit(default)
            setattr(self, attr, edit)
            btn = QPushButton("Browse")
            btn.clicked.connect(lambda checked, e=edit, a=(True if "Lib" in label else False): self.browse_dir(e, append=a))
            lay.addWidget(edit); lay.addWidget(btn)
            project_layout.addLayout(lay)

        self.project_name_input = QLineEdit()
        project_layout.addWidget(QLabel("Projectnaam:"))
        project_layout.addWidget(self.project_name_input)

        self.mesh_project_input = QLineEdit()
        btn_scan = QPushButton("📁 Scan Project")
        btn_scan.clicked.connect(self.scan_meshroom_project)
        lay_s = QHBoxLayout(); lay_s.addWidget(self.mesh_project_input); lay_s.addWidget(btn_scan)
        project_layout.addWidget(QLabel("Meshroom Project:"))
        project_layout.addLayout(lay_s)

        self.sfm_selector = QComboBox()
        project_layout.addWidget(QLabel("Geselecteerde SfM:"))
        project_layout.addWidget(self.sfm_selector)

        self.photo_input = QLineEdit()
        btn_photo = QPushButton("Browse Foto's")
        btn_photo.clicked.connect(lambda: self.browse_dir(self.photo_input))
        lay_p = QHBoxLayout(); lay_p.addWidget(self.photo_input); lay_p.addWidget(btn_photo)
        project_layout.addWidget(QLabel("Foto Map:"))
        project_layout.addLayout(lay_p)
        project_group.setLayout(project_layout)
        layout.addWidget(project_group)

        # --- 3. PROGRESS & CPU ---
        progress_group = QGroupBox("3. Status & Progressie")
        progress_layout = QVBoxLayout()
        
        self.pipe_progress = QProgressBar()
        self.pipe_progress.setRange(0, 6)
        self.pipe_progress.setValue(0)
        self.pipe_progress.setFormat("Pipeline Stap: %v / 6")
        self.pipe_progress.setStyleSheet("QProgressBar::chunk { background-color: #2196f3; }")
        
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setStyleSheet("QProgressBar::chunk { background-color: #4caf50; }")
        
        progress_layout.addWidget(QLabel("Totale Voortgang:"))
        progress_layout.addWidget(self.pipe_progress)
        progress_layout.addWidget(QLabel("Live CPU Belasting:"))
        progress_layout.addWidget(self.cpu_bar)
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        self.btn_run = QPushButton("🚀 START PIPELINE")
        self.btn_run.setStyleSheet("background-color: #1b5e20; color: white; padding: 15px; font-weight: bold;")
        self.btn_run.clicked.connect(self.run_full_pipeline)
        layout.addWidget(self.btn_run)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("background-color: #000; color: #0f0; font-family: 'Monospace';")
        layout.addWidget(self.log_output)

    # --- LOGICA ---

    def validate_selected_image(self):
        engine = self.image_selector.currentText()
        if not engine: return
        try:
            res = subprocess.run(f"docker run --rm {engine} ldconfig -p | grep opencv", shell=True, capture_output=True, text=True, timeout=5)
            self.validation_label.setText("✅ Geschikt" if res.returncode == 0 else "❌ Ongeschikt")
            self.validation_label.setStyleSheet(f"color: {'#4caf50' if res.returncode == 0 else '#f44336'}; font-weight: bold;")
        except: self.validation_label.setText("❓ Onbekend")

    def refresh_docker_images(self):
        self.image_selector.clear()
        try:
            res = subprocess.run(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"], capture_output=True, text=True)
            images = res.stdout.strip().split('\n')
            for img in images:
                if img.strip(): self.image_selector.addItem(img.strip())
            self.btn_build_docker.setVisible(not any("vanvoorn-openmvs" in s for s in images))
            idx = self.image_selector.findText("vanvoorn-openmvs:latest")
            if idx != -1: self.image_selector.setCurrentIndex(idx)
        except: pass

    def build_custom_image(self):
        self.log("\n--- BOUWEN DOCKER IMAGE ---")
        df = "FROM ubuntu:24.04\nRUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y libopencv-dev libjxl-dev libcgal-dev libceres-dev libsuitesparse-dev libboost-iostreams-dev libboost-program-options-dev libboost-system-dev libboost-serialization-dev libboost-python-dev && rm -rf /var/lib/apt/lists/*"
        with open("Dockerfile_temp", "w") as f: f.write(df)
        if subprocess.run("docker build -t vanvoorn-openmvs:latest -f Dockerfile_temp .", shell=True).returncode == 0:
            self.refresh_docker_images()
        os.remove("Dockerfile_temp")

    def scan_meshroom_project(self, silent=False):
        if not silent:
            d = QFileDialog.getExistingDirectory(self, "Selecteer Project")
            if d: self.mesh_project_input.setText(d)
        root = self.mesh_project_input.text()
        self.sfm_selector.clear()
        files = glob.glob(os.path.join(root, "MeshroomCache", "ConvertSfMFormat", "**", "*.sfm"), recursive=True)
        files.sort(key=os.path.getmtime, reverse=True)
        for f in files:
            m = datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M')
            self.sfm_selector.addItem(f"[{m}] {f[-60:]}", f)

    def browse_dir(self, edit, append=False):
        d = QFileDialog.getExistingDirectory(self, "Selecteer Map")
        if d: edit.setText(f"{edit.text()}:{d}" if append and edit.text() else d)

    def update_cpu_usage(self):
        u = psutil.cpu_percent()
        self.cpu_bar.setValue(int(u))
        self.cpu_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {'#f44336' if u > 85 else '#4caf50'}; }}")

    def log(self, text):
        self.log_output.append(text); self.log_output.ensureCursorVisible(); QApplication.processEvents()

    def run_command(self, cmd, env=None):
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, text=True)
        for line in p.stdout: self.log(line.strip())
        p.wait()
        return p.returncode

    def load_settings(self):
        if os.path.exists(self.config_file):
            c = configparser.ConfigParser(); c.read(self.config_file)
            if 'SETTINGS' in c:
                s = c['SETTINGS']
                self.mesh_bin_input.setText(s.get('mesh_bin', ''))
                self.mesh_lib_input.setText(s.get('mesh_lib', ''))
                self.photo_input.setText(s.get('photo_dir', ''))
                self.project_name_input.setText(s.get('project_name', ''))
                self.mesh_project_input.setText(s.get('mesh_project', ''))
                if self.mesh_project_input.text(): self.scan_meshroom_project(silent=True)

    def run_full_pipeline(self):
        config = configparser.ConfigParser()
        config['SETTINGS'] = { 'mesh_bin': self.mesh_bin_input.text(), 'mesh_lib': self.mesh_lib_input.text(), 'photo_dir': self.photo_input.text(), 'project_name': self.project_name_input.text(), 'mesh_project': self.mesh_project_input.text() }
        with open(self.config_file, 'w') as f: config.write(f)

        engine = self.image_selector.currentText()
        sfm = self.sfm_selector.currentData()
        name = self.project_name_input.text().strip()
        photo_dir = self.photo_input.text().strip()
        bin_p = self.mesh_bin_input.text().strip()
        lib_p = self.mesh_lib_input.text().strip()

        if not sfm or not name: return
        self.pipe_progress.setValue(0)
        work_dir = os.path.join(self.base_dir, "projects", name)
        colmap_dir = os.path.join(work_dir, "colmap_data")
        if os.path.exists(work_dir): shutil.rmtree(work_dir)
        os.makedirs(work_dir, exist_ok=True)

        env = os.environ.copy(); env["LD_LIBRARY_PATH"] = lib_p; env["ALICEVISION_ROOT"] = os.path.dirname(bin_p)

        # STAP 1
        self.log("--- STAP 1: Meshroom Export ---")
        if self.run_command(f"'{bin_p}/aliceVision_exportColmap' -i '{sfm}' -o '{colmap_dir}'", env) != 0: return
        self.pipe_progress.setValue(1)

        # STAP 2
        self.log("--- STAP 2: Patching ---")
        src_cam = next((os.path.join(r, "cameras.txt") for r, d, f in os.walk(colmap_dir) if "cameras.txt" in f), None)
        if src_cam:
            ds = os.path.join(colmap_dir, "sparse"); os.makedirs(ds, exist_ok=True)
            with open(src_cam, 'r') as f: lines = f.readlines()
            with open(os.path.join(ds, "cameras.txt"), 'w') as f:
                for l in lines:
                    if not l.startswith("#") and l.strip():
                        p = l.split()
                        if len(p) >= 8: f.write(f"{p[0]} PINHOLE {p[2]} {p[3]} {p[4]} {p[5]} {p[6]} {p[7]}\n")
                    else: f.write(l)
            for f in ["images.txt", "points3D.txt"]: shutil.copy(os.path.join(os.path.dirname(src_cam), f), os.path.join(ds, f))
            os.makedirs(os.path.join(colmap_dir, "images"), exist_ok=True)
            subprocess.run(f"cp '{photo_dir}'/*.JPG '{colmap_dir}/images/' 2>/dev/null", shell=True)
            subprocess.run(f"cp '{photo_dir}'/*.jpg '{colmap_dir}/images/' 2>/dev/null", shell=True)
        self.pipe_progress.setValue(2)

        # DOCKER STAPPEN
        steps = [
            ("InterfaceCOLMAP", f"/pipeline/bin/InterfaceCOLMAP -i colmap_data -o model.mvs"),
            ("DensifyPointCloud", f"/pipeline/bin/DensifyPointCloud model.mvs --estimate-roi 0"),
            ("ReconstructMesh", f"/pipeline/bin/ReconstructMesh model_dense.mvs"),
            ("TextureMesh", f"/pipeline/bin/TextureMesh model_dense.mvs --mesh-file model_dense_mesh.ply --export-type obj")
        ]
        
        for i, (label, cmd) in enumerate(steps, 3):
            self.log(f"--- STAP {i}: {label} ---")
            d_cmd = f"docker run --rm -v '{self.base_dir}':/pipeline {engine} bash -c 'cd /pipeline/projects/{name} && {cmd}'"
            if self.run_command(d_cmd) != 0: return
            self.pipe_progress.setValue(i)

        self.log("\n[SUCCES] Project Voltooid!")

if __name__ == "__main__":
    app = QApplication(sys.argv); window = PhotogrammetryApp(); window.show(); sys.exit(app.exec())
