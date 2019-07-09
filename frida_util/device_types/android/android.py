
import logging
logger = logging.getLogger(__name__)

import frida
import shlex
import os
import subprocess

from .. import BaseDevice

class AndroidDevice(BaseDevice):
    def __init__(self, id=None, type=None):
        """Describes and Android device.

        Args:
            id (str, optional): Unique ID for this android device
            type (str, optional): Connection type for this device.

        Examples:
            AndroidDevice(id="emulator-5554")
            AndroidDevice(type="usb")
        """
        self.id = id
        self.type = type.lower()
        self._select_device()

        # Make sure we can have root
        self.adb("root")

        self.start_frida_server()

    def _select_device(self):
        """Figure out which device we want to use."""

        if self.id:
            self.device = frida.get_device(self.id)
            return

        if self.type == "usb":
            usbs = [x for x in frida.enumerate_devices() if x.type == 'usb']
            if usbs == []:
                error = "Cannot find USB device."
                logger.error(error)
                raise Exception(error)

            if len(usbs) > 1:
                logger.warn("Found more than 1 usb device. Selecting first one...")

            self.device = usbs[0]
            self.id = self.device.id
            return

        error = "Couldn't find the device you requested..."
        logger.error(error)
        raise Exception(error)

    def start_frida_server(self):
        if self.frida_server_running:
            logger.info("Frida server already running on this device.")
            return
        
        logger.info("Attempting to start up Frida server on device.")

        # Download the server
        server_bin = common.download_frida_server("android", self.arch)

        print("Pushing frida server ... ", flush=True)
        self.adb("push " + server_bin + " /data/local/tmp/frida-server")

        print("Starting frida server ... ", flush=True)
        self.adb("shell chmod +x /data/local/tmp/frida-server")
        self.adb(["shell", "nohup /data/local/tmp/frida-server &>/dev/null &"])

        # Clean up after ourselves
        os.unlink(server_bin)

    def adb(self, command):
        """Helper wrapper to run the command on your instance."""

        if isinstance(command, str):
            command = shlex.split(command)

        return subprocess.check_output(["adb", "-s", self.device.id] + command)

    def spawn(self, application, gated=True, load_symbols=None):
        """Spawn the given application.

        Args:
            application (str): Full application name (i.e.: com.android.calculator2)
            gated (bool, optional): If True, pause application immediately on loading
                This allows hooking prior to program startup.
            load_symbols (list): Only load symbols for the given modules. Same
                usage as frida_util.Process

        Returns:
            frida_util.Process: Process instantitation for this new process.
        """
        
        if gated:
            self.device.enable_spawn_gating()
        else:
            self.device.disable_spawn_gating()

        if isinstance(application, frida._frida.Application):
            application = application.identifier

        pid = self.device.spawn(application)

        if not gated:
            # Sometimes it gates anyway
            self.device.resume(pid)

        return Process(pid, device=self, load_symbols=load_symbols)

    def install(self, package):
        """Install package onto android device.

        Args:
            package (str): Path to package to install.
        """

        package = os.path.abspath(package)

        if not os.path.isfile(package):
            logger.error("Cannot find apk to install.")
            return False

        return self.adb("install " + package)

    def uninstall(self, application):
        """Uninstall the given application.
        
        Args:
            application (str): Application to uninstall

        Example:
            android.uninstall("com.android.calculator2")
        """

        if isinstance(application, frida._frida.Application):
            application = application.identifier

        return self.adb("uninstall " + application)

    def __repr__(self):
        attrs = ['AndroidDevice', self.id]
        return '<' + ' '.join(attrs) + '>'

    @property
    def applications(self):
        return AndroidApplications(self)

    @property
    def frida_server_running(self):
        try:
            self.device.enumerate_applications()
            return True
        except frida.ServerNotRunningError:
            return False

    @property
    def arch(self):
        """Returns the arch of this android device."""
        try:
            return self.__arch
        except:
            #arch = subprocess.check_output(["adb", "-s", self.device.id, "shell", "uname", "-m"]).strip().decode()
            arch = self.adb("shell uname -m").strip().decode()

            if arch not in uname_standard:
                error = "Unhandled arch standardization of {}".format(arch)
                logger.error(error)
                raise Exception(error)

            self.__arch = uname_standard[arch]
            return self.__arch

from .applications import AndroidApplications
from ... import common
from .. import uname_standard
from ...process import Process

