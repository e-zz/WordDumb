#!/usr/bin/env python3
import shutil
from pathlib import Path
import subprocess
import traceback

from calibre.gui2 import FunctionDispatcher
from calibre.constants import ismacos, iswindows
from calibre.gui2.dialogs.message_box import JobError

from .database import get_ll_path, get_x_ray_path
from .metadata import get_asin_etc


class SendFile:
    def __init__(self, gui, data, is_android, notif):
        self.gui = gui
        self.device_manager = gui.device_manager
        self.notif = notif
        (
            self.book_id,
            self.asin,
            self.book_path,
            self.mi,
            _,
            self.book_fmt,
            self.acr,
        ) = data
        self.ll_path = get_ll_path(self.asin, self.book_path)
        self.x_ray_path = get_x_ray_path(self.asin, self.book_path)
        self.is_android = is_android
        if self.acr is None:
            self.acr = "_"

    # use some code from calibre.gui2.device:DeviceMixin.upload_books
    def send_files(self, job):
        if self.is_android:
            try:
                self.push_files_to_android()
            except subprocess.CalledProcessError as e:
                JobError(self.gui).show_error(
                    "adb failed", e.stderr, det_msg=traceback.format_exc() + e.stderr
                )
            self.gui.status_bar.show_message(self.notif)
            return

        if job is not None:
            if job.failed:
                self.gui.job_exception(job, dialog_title="Upload book failed")
                return
            self.gui.books_uploaded(job)
            if self.book_fmt == "EPUB":
                self.gui.status_bar.show_message(self.notif)
                Path(self.book_path).unlink()
                return

        [has_book, _, _, _, paths] = self.gui.book_on_device(self.book_id)
        if has_book and self.book_fmt != "EPUB":
            if job is None:
                get_asin_etc(self.book_path, self.book_fmt, self.mi, self.asin)
            # /Volumes/Kindle
            device_prefix = self.device_manager.device._main_prefix
            device_book_path = Path(device_prefix).joinpath(next(iter(paths)))
            self.move_file_to_device(self.ll_path, device_book_path)
            self.move_file_to_device(self.x_ray_path, device_book_path)
            self.gui.status_bar.show_message(self.notif)
        elif job is None or self.book_fmt == "EPUB":
            # upload book and cover to device
            self.gui.update_thumbnail(self.mi)
            job = self.device_manager.upload_books(
                FunctionDispatcher(self.send_files),
                [self.book_path],
                [Path(self.book_path).name],
                on_card=None,
                metadata=[self.mi],
                titles=[i.title for i in [self.mi]],
                plugboards=self.gui.current_db.new_api.pref("plugboards", {}),
            )
            self.gui.upload_memory[job] = ([self.mi], None, None, [self.book_path])

    def move_file_to_device(self, file_path, device_book_path):
        if not file_path.is_file():
            return
        sidecar_folder = device_book_path.parent.joinpath(
            f"{device_book_path.stem}.sdr"
        )
        if not sidecar_folder.is_dir():
            sidecar_folder.mkdir()
        dst_path = sidecar_folder.joinpath(file_path.name)
        if dst_path.is_file():
            dst_path.unlink()
        # Python 3.9 accepts path-like object, calibre uses 3.8
        shutil.move(str(file_path), str(dst_path), shutil.copy)

    def push_files_to_android(self):
        r = run_adb(["shell", "pm", "list", "packages", "com.amazon.kindle"])
        result = r.stdout.strip()
        if len(result.split(":")) > 1:
            package_name = result.split(":")[1]
        else:
            return
        device_book_folder = f"/sdcard/Android/data/{package_name}/files/"
        run_adb(
            [
                "push",
                self.book_path,
                f"{device_book_folder}/{Path(self.book_path).name}",
            ]
        )
        if self.x_ray_path.exists():
            run_adb(
                [
                    "push",
                    self.x_ray_path,
                    f"{device_book_folder}/{self.asin}/XRAY.{self.asin}.{self.acr}.db",
                ]
            )
            self.x_ray_path.unlink()
        if self.ll_path.exists():
            run_adb(["root"])
            run_adb(
                [
                    "push",
                    self.ll_path,
                    f"/data/user/0/{package_name}/databases/WordWise.en.{self.asin}.{self.acr.replace('!', '_')}.db",
                ]
            )
            self.ll_path.unlink()


def device_connected(gui, book_fmt):
    if gui.device_manager.is_device_present and (
        book_fmt == "EPUB"
        or getattr(gui.device_manager.device, "VENDOR_NAME", None) == "KINDLE"
    ):
        return True
    if book_fmt == "KFX" and adb_connected():
        return "android"
    return False


def adb_connected():
    r = run_adb(["devices"])
    return r.stdout.strip().endswith("device") if r else False


def run_adb(args):
    adb = "/usr/local/bin/adb" if ismacos else "adb"
    if not shutil.which(adb):
        return
    args.insert(0, adb)
    if iswindows:
        return subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        return subprocess.run(args, check=True, capture_output=True, text=True)
