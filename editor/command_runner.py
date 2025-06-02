from PyQt5.QtCore import QObject, pyqtSignal, QProcess

class CommandRunner(QObject):
    finished = pyqtSignal(str, str)  # Signal to send stdout and stderr on completion

    def run_command(self, command):
        self.process = QProcess()
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.on_ready_read)
        self.process.finished.connect(self.on_finished)
        self.process.start(command)

    def on_ready_read(self):
        output = self.process.readAllStandardOutput().data().decode()
        self.stdout += output

    def on_finished(self):
        self.finished.emit(self.stdout, '')

    def kill_process(self):
        self.process.kill()

    def run_command_sync(self, command):
        self.stdout = ''
        self.run_command(command)
        self.process.waitForFinished()
        return self.stdout 