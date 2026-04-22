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
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal

# --- WORKER THREAD FOR SMOOTH GUI AND PIPELINE CONTROL ---
class PipelineWorker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool)

    def __init__(self, steps):
        super().__init__()
        self.steps = steps  # List of (label, cmd, env)
        self.is_running = True
        self.current_process = None

    def run(self):
        for i, (label, cmd, env) in enumerate(self.steps):
            if not self.is_running:
                break
            
            if cmd == "INTERNAL_PATCH":
                self.progress_signal.emit(i + 1)
                continue

            self.log_signal.emit(f"\n>>> STARTING STEP {i+1}: {label}")
            self.progress_signal.emit(i + 1)
            
            self.current_process = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, env=env, text=True
            )

            for line in self.current_process.stdout:
                if not self.is_running:
                    self.current_process.terminate()
                    break
                self.log_signal.emit(line.strip())

            self.current_process.wait()
            if self.current_process.returncode != 0 and self.is_running:
                self.log_signal.emit(f"\n[ERROR] {label} failed with code {self.current_process.returncode}")
                self.finished_signal.emit(False)
                return

        self.finished_signal.emit(self.is_running)

    def stop(self):
        self.is_running = False
        if self.current_process:
            self.current_process.terminate()

# --- MAIN APPLICATION ---
class PhotogrammetryApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Van Voorn Photogrammetry Engine - Smart Guard Edition")
        self.resize(1150, 950)

        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(self.base_dir, "config.ini")
        self.worker = None
        
        self.init_ui()
        self.load_settings()
        self.refresh_docker_images()
        
        # Check for premade container on boot
        QTimer.singleShot(500, self.check_for_premade_container)
        
        # CPU Monitor Timer
        self.cpu_timer = QTimer()
        self.cpu_timer.timeout.connect(self.update_cpu_usage)
        self.cpu_timer.start(1000)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # --- 1. DOCKER ENGINE ---
        docker_group = QGroupBox("1. Docker Engine Management")
        d_lay = QHBoxLayout()
        self.image_selector = QComboBox()
        self.image_selector.currentTextChanged.connect(self.validate_selected_image)
        self.validation_label = QLabel("-")
        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.clicked.connect(self.refresh_docker_images)
        self.btn_build = QPushButton("🛠️ Build Optimized Engine")
        self.btn_build.setStyleSheet("background-color: #0d47a1; color: white; font-weight: bold;")
        self.btn_build.clicked.connect(self.build_optimized_image)
        
        d_lay.addWidget(QLabel("Engine:")); d_lay.addWidget(self.image_selector)
        d_lay.addWidget(self.validation_label); d_lay.addWidget(btn_refresh); d_lay.addWidget(self.btn_build)
        docker_group.setLayout(d_lay); layout.addWidget(docker_group)

        # --- 2. MESHROOM & PROJECT ---
        proj_group = QGroupBox("2. Meshroom & Project Configuration")
        p_lay = QVBoxLayout()

        self.mesh_bin_input = QLineEdit("/mnt/VG_00/Portable.APPS/Meshroom/Meshroom-2025.1.0/aliceVision/bin")
        self.mesh_lib_input = QLineEdit("/mnt/VG_00/Portable.APPS/Meshroom/Meshroom-2025.1.0/aliceVision/lib:/mnt/VG_00/Portable.APPS/Meshroom/Meshroom-2025.1.0/lib")
        self.template_input = QLineEdit("/home/peter/Photogrammetry_Pipeline/template/meshroom.template.mg")
        
        for lbl, edit in [("Bin Path:", self.mesh_bin_input), ("Lib Path:", self.mesh_lib_input), ("Meshroom Template:", self.template_input)]:
            p_lay.addWidget(QLabel(lbl)); p_lay.addWidget(edit)

        self.project_name_input = QLineEdit()
        p_lay.addWidget(QLabel("Project Name (Output folder):")); p_lay.addWidget(self.project_name_input)

        self.mesh_project_input = QLineEdit()
        btn_scan = QPushButton("📁 Scan Project"); btn_scan.clicked.connect(self.scan_meshroom_project)
        scan_lay = QHBoxLayout(); scan_lay.addWidget(self.mesh_project_input); scan_lay.addWidget(btn_scan)
        p_lay.addWidget(QLabel("Meshroom Project Directory:")); p_lay.addLayout(scan_lay)

        self.sfm_selector = QComboBox()
        p_lay.addWidget(QLabel("Select SfM / Camera File:")); p_lay.addWidget(self.sfm_selector)

        self.photo_input = QLineEdit()
        btn_ph = QPushButton("Browse Photos"); btn_ph.clicked.connect(lambda: self.browse_dir(self.photo_input))
        ph_lay = QHBoxLayout(); ph_lay.addWidget(self.photo_input); ph_lay.addWidget(btn_ph)
        p_lay.addWidget(QLabel("Original Photo Directory:")); p_lay.addLayout(ph_lay)

        proj_group.setLayout(p_lay); layout.addWidget(proj_group)

        # --- 3. PROGRESS ---
        self.pipe_progress = QProgressBar(); self.pipe_progress.setRange(0, 6)
        self.cpu_bar = QProgressBar()
        layout.addWidget(QLabel("Pipeline Progress:")); layout.addWidget(self.pipe_progress)
        layout.addWidget(QLabel("Live CPU Usage:")); layout.addWidget(self.cpu_bar)

        # --- CONTROLS ---
        btn_lay = QHBoxLayout()
        self.btn_run = QPushButton("🚀 START PIPELINE")
        self.btn_run.setStyleSheet("background-color: #1b5e20; color: white; height: 45px; font-weight: bold;")
        self.btn_run.clicked.connect(self.run_full_pipeline)
        
        self.btn_stop = QPushButton("🛑 STOP")
        self.btn_stop.setStyleSheet("background-color: #b71c1c; color: white; height: 45px; font-weight: bold;")
        self.btn_stop.setEnabled(False); self.btn_stop.clicked.connect(self.stop_pipeline)
        
        btn_lay.addWidget(self.btn_run); btn_lay.addWidget(self.btn_stop)
        layout.addLayout(btn_lay)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("background-color: #000; color: #0f0; font-family: 'Monospace'; font-size: 10pt;")
        layout.addWidget(self.log_output)

    # --- FUNCTIONS ---

    def log(self, text):
        self.log_output.append(text)
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def update_cpu_usage(self):
        u = psutil.cpu_percent()
        self.cpu_bar.setValue(int(u))
        self.cpu_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {'#f44336' if u > 85 else '#4caf50'}; }}")

    def check_for_premade_container(self):
        engine_name = "vanvoorn-openmvs:latest"
        if self.image_selector.findText(engine_name) != -1: return

        premade_path = os.path.join(self.base_dir, "premade.dockercontainer")
        tar_files = glob.glob(os.path.join(premade_path, "*.tar"))
        if tar_files:
            tar_file = tar_files[0]
            reply = QMessageBox.question(self, "Import Premade Engine?", f"A premade Docker engine was found:\n{os.path.basename(tar_file)}\n\nImport it now?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.btn_run.setEnabled(False)
                self.worker = PipelineWorker([("Importing Engine", f"docker load < '{tar_file}'", None)])
                self.worker.log_signal.connect(self.log)
                self.worker.finished_signal.connect(lambda: [self.refresh_docker_images(), self.btn_run.setEnabled(True)])
                self.worker.start()

    def build_optimized_image(self):
        self.log("\n--- BUILDING OPTIMIZED ENGINE (Cleaning caches to save space) ---")
        dockerfile = (
            "FROM ubuntu:24.04\n"
            "RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "
            "libopencv-video-dev libopencv-imgproc-dev libopencv-highgui-dev libjxl-dev libcgal-dev libceres-dev "
            "libsuitesparse-dev libboost-iostreams-dev libboost-program-options-dev libboost-system-dev "
            "libboost-serialization-dev libboost-python-dev && "
            "apt-get clean && rm -rf /var/lib/apt/lists/*"
        )
        temp_df = os.path.join(self.base_dir, "Dockerfile_temp")
        with open(temp_df, "w") as f: f.write(dockerfile)
        self.btn_run.setEnabled(False)
        self.worker = PipelineWorker([("Building Engine", f"docker build -t vanvoorn-openmvs:latest -f '{temp_df}' .", None)])
        self.worker.log_signal.connect(self.log)
        self.worker.finished_signal.connect(lambda: [self.refresh_docker_images(), self.btn_run.setEnabled(True), os.remove(temp_df)])
        self.worker.start()

    def validate_selected_image(self):
        engine = self.image_selector.currentText()
        if not engine: return
        try:
            res = subprocess.run(f"docker run --rm {engine} ldconfig -p | grep opencv", shell=True, capture_output=True, text=True, timeout=5)
            self.validation_label.setText("✅ Compatible" if res.returncode == 0 else "❌ Incompatible")
            self.validation_label.setStyleSheet(f"color: {'#4caf50' if res.returncode == 0 else '#f44336'}; font-weight: bold;")
        except: self.validation_label.setText("❓")

    def refresh_docker_images(self):
        self.image_selector.clear()
        try:
            res = subprocess.run(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"], capture_output=True, text=True)
            for img in res.stdout.strip().split('\n'):
                if img: self.image_selector.addItem(img)
            idx = self.image_selector.findText("vanvoorn-openmvs:latest")
            if idx != -1: self.image_selector.setCurrentIndex(idx)
        except: pass

    def scan_meshroom_project(self, silent=False):
        if not silent:
            d = QFileDialog.getExistingDirectory(self, "Select Project Folder")
            if d: self.mesh_project_input.setText(d)
        root = self.mesh_project_input.text().strip()
        self.sfm_selector.clear()
        files = glob.glob(os.path.join(root, "MeshroomCache", "**", "*.*"), recursive=True)
        sfm_files = [f for f in files if f.lower().endswith(('.sfm', '.abc'))]
        sfm_files.sort(key=os.path.getmtime, reverse=True)
        for f in sfm_files:
            m = datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M')
            self.sfm_selector.addItem(f"[{m}] {os.path.basename(f)} ({f.split(os.sep)[-2][:8]})", f)

    def browse_dir(self, edit):
        d = QFileDialog.getExistingDirectory(self, "Select Folder")
        if d: edit.setText(d)

    def save_settings(self):
        c = configparser.ConfigParser()
        c['S'] = {'bin': self.mesh_bin_input.text(), 'lib': self.mesh_lib_input.text(), 'tmpl': self.template_input.text(), 'p': self.mesh_project_input.text(), 'ph': self.photo_input.text(), 'nm': self.project_name_input.text()}
        with open(self.config_file, 'w') as f: c.write(f)

    def load_settings(self):
        if os.path.exists(self.config_file):
            c = configparser.ConfigParser(); c.read(self.config_file)
            if 'S' in c:
                s = c['S']
                self.mesh_bin_input.setText(s.get('bin', '')); self.mesh_lib_input.setText(s.get('lib', ''))
                self.template_input.setText(s.get('tmpl', '')); self.mesh_project_input.setText(s.get('p', ''))
                self.photo_input.setText(s.get('ph', '')); self.project_name_input.setText(s.get('nm', ''))
                if self.mesh_project_input.text(): self.scan_meshroom_project(silent=True)

    def stop_pipeline(self):
        if self.worker:
            self.worker.stop()
            self.log("\n🛑 PIPELINE STOPPED BY USER")
            self.btn_run.setEnabled(True); self.btn_stop.setEnabled(False)

    def run_full_pipeline(self):
        self.save_settings()
        sfm = self.sfm_selector.currentData(); name = self.project_name_input.text().strip()
        bin_p = self.mesh_bin_input.text().strip(); lib_p = self.mesh_lib_input.text().strip()
        photo_dir = self.photo_input.text().strip(); engine = self.image_selector.currentText()

        if not sfm or not name or not engine:
            QMessageBox.critical(self, "Error", "Missing configuration!"); return

        self.btn_run.setEnabled(False); self.btn_stop.setEnabled(True)
        self.pipe_progress.setValue(0)
        
        work_dir = os.path.join(self.base_dir, "projects", name)
        colmap_dir = os.path.join(work_dir, "colmap_data")
        if os.path.exists(work_dir): shutil.rmtree(work_dir)
        os.makedirs(work_dir, exist_ok=True)

        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = lib_p
        env["ALICEVISION_ROOT"] = os.path.dirname(bin_p)
        env["ALICEVISION_SENSOR_DB"] = os.path.join(env["ALICEVISION_ROOT"], "share/aliceVision/cameraSensors.db")

        steps = [
            ("AliceVision Export", f"'{bin_p}/aliceVision_exportColmap' -i '{sfm}' -o '{colmap_dir}'", env),
            ("Patching", "INTERNAL_PATCH", None),
            ("InterfaceCOLMAP", f"docker run --rm -v '{self.base_dir}':/pipeline {engine} bash -c 'cd /pipeline/projects/{name} && /pipeline/bin/InterfaceCOLMAP -i colmap_data -o model.mvs'", None),
            ("DensifyPointCloud", f"docker run --rm -v '{self.base_dir}':/pipeline {engine} bash -c 'cd /pipeline/projects/{name} && /pipeline/bin/DensifyPointCloud model.mvs --estimate-roi 0'", None),
            ("ReconstructMesh", f"docker run --rm -v '{self.base_dir}':/pipeline {engine} bash -c 'cd /pipeline/projects/{name} && /pipeline/bin/ReconstructMesh model_dense.mvs'", None),
            ("TextureMesh", f"docker run --rm -v '{self.base_dir}':/pipeline {engine} bash -c 'cd /pipeline/projects/{name} && /pipeline/bin/TextureMesh model_dense.mvs --mesh-file model_dense_mesh.ply --export-type obj'", None)
        ]

        self.worker = PipelineWorker(steps)
        self.worker.log_signal.connect(self.log)
        def handle_progress(step):
            self.pipe_progress.setValue(step)
            if step == 2: self.patch_colmap(colmap_dir, photo_dir)
        self.worker.progress_signal.connect(handle_progress)
        self.worker.finished_signal.connect(self.pipeline_finished); self.worker.start()

    def patch_colmap(self, colmap_dir, photo_dir):
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
            for fn in ["images.txt", "points3D.txt"]:
                src_f = os.path.join(os.path.dirname(src_cam), fn)
                if os.path.exists(src_f): shutil.copy(src_f, os.path.join(ds, fn))
            img_dst = os.path.join(colmap_dir, "images"); os.makedirs(img_dst, exist_ok=True)
            self.log(f"Syncing images to {img_dst}...")
            subprocess.run(f"cp '{photo_dir}'/*.JPG '{img_dst}/' 2>/dev/null", shell=True)
            subprocess.run(f"cp '{photo_dir}'/*.jpg '{img_dst}/' 2>/dev/null", shell=True)

    def pipeline_finished(self, success):
        self.btn_run.setEnabled(True); self.btn_stop.setEnabled(False)
        if success: self.log("\n✅ PROJECT COMPLETED!"); self.pipe_progress.setValue(6)

if __name__ == "__main__":
    app = QApplication(sys.argv); window = PhotogrammetryApp(); window.show(); sys.exit(app.exec())
