
import logging
logger = logging.getLogger(__name__)

from .. import Engine

class FridaEngine(Engine):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._scripts = []
        self.session = None

    def start_session(self):

        self._process._spawned_pid = None

        if self._process._spawn_target is not None:
            print("Spawning file\t\t\t... ", end='', flush=True)
            self._process._spawned_pid = self._process.device.device.spawn(self._process._spawn_target, argv=self._process.argv, envp=self._process._envp)
            cprint("[ DONE ]", "green")

        print('Attaching to the session\t... ', end='', flush=True)

        try:
            # Default attach to what we just spawned
            self.session = self._process.device.device.attach(self._process._spawned_pid or self._process.target)
        except frida.ProcessNotFoundError:
            logger.error('Could not find that target process to attach to!')
            exit(1)

        print(colorama.Fore.GREEN + '[ DONE ]' + colorama.Style.RESET_ALL)


    def load_js(self, name):
        with open(os.path.join(here, "..", "..", "js", name), "r") as f:
            return f.read().strip()


    def run_script_generic(self, script_name, raw=False, replace=None,
            unload=False, runtime='duk', on_message=None, timeout=None,
            context=None, onComplete=None, include_js=None):
        """Run scripts that don't require anything special.
        
        Args:
            script_name (str): What script to load from the js directory
            raw (bool, optional): Should the script_name actually be considered
                the script contents?
            replace (dict, optional): Replace key strings from dictionary with
                value into script.
            unload (bool, optional): Auto unload the script. Set to true if the
                script is fully synchronous.
            runtime (str, optional): Runtime to use for this script, either
                'duk' or 'v8'.
            on_message(callable, optional): Set the on_message handler to this
                instead.
            timeout (int, optional): Modify timeout (default is 60 seconds).
                Note, this will cause the script to run async. 0 == no timeout
            context (Context, optional): Execute this script under a given
                context.
            onComplete (str, optional): If defined, this method will pause
                until the given onComplete string is returned. Basically
                allowing run_script_generic to return all things from an async
                script.
            include_js (tuple, optional): If defined, the given js files will
                be loaded into the script before the main script. This is to
                be used for shared functionality. 

        Returns:
            tuple: msg, data return from the script
        """


        msg = []
        data = []
        if include_js is None:
            include_js = ("dispose.js", "send_batch.js", "timeless.js", "telescope.js")

        # HACK: Using list for completed to make passing data back from async
        # function simpler.
        completed = [] # For use with async scripts

        if not on_message is None and not callable(on_message):
            logger.error('on_message handler must be callable.')
            return None

        def on_msg(m, d):

            if m['type'] == 'error':
                logger.error("Script Run Error: " + pprint.pformat(m['description']))
                logger.debug(pprint.pformat(m))
                return
            
            # Async is done
            if onComplete is not None and m['payload'] == onComplete:
                completed.append(True)
                return

            logger.debug("on_message: {}".format([m,d]))

            msg.append(m['payload'] if 'payload' in m else None)
            data.append(d)

        on_message = on_msg if on_message is None else on_message

        js = ""

        if include_js is not None:

            if not isinstance(include_js, (tuple, list)):
                include_js = (include_js,)

            for js_file in include_js:
                js += self.load_js(js_file) + "\n"

        if not raw:
            js += self.load_js(script_name)
        else:
            js += script_name

        if replace is not None:
            assert type(replace) == dict, "Unexpected replace type of {}".format(type(replace))

            for key, value in replace.items():
                js = js.replace(key, value)

        if timeout is not None:
            js = "setTimeout(function() {" + js + "}," + str(timeout) + ")"
            # Forcing unload to false since we don't know if it's done.
            unload = False

        # Let context decide when to run this.
        if context is not None:
            # Processing is done, let context know.
            return context.run_script_generic(script_name)

        logger.debug("Running script: %s", js)

        script = self.session.create_script(js, runtime=runtime)

        script.on('message', on_message)

        try:
            script.load()
        except Exception as e:
            logger.error("Error running script! " + str(e))
            script.unload()
            return

        # If we're async, wait until we're done
        # This needs to happen before unlink so we ensure we get all messages
        while onComplete is not None and completed == []:
            time.sleep(0.01)
        
        if unload:
            # TODO: Maybe not do this for every unload? Not sure performance impact...
            try:
                script.exports.dispose()
            except frida.core.RPCException as e:
                # We're OK if this didn't exist.
                if "unable to find method" not in e.args[0]:
                    raise
            script.unload()
        else:
            # Inserting instead of appending since earlier scripts need to be unloaded later
            self._scripts.insert(0, [script, js])

        return msg, data

Engine = FridaEngine

import os
import pprint
import frida
import colorama
import time
from termcolor import cprint, colored

here = os.path.dirname(os.path.abspath(__file__))
