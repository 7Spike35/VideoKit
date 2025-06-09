let isRecording = false;

document.getElementById('muteButton').addEventListener('click', () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) {
      chrome.tabs.sendMessage(tabs[0].id, { action: 'mute' }, (response) => {
        if (chrome.runtime.lastError) {
          updateStatus('静音失败: ' + chrome.runtime.lastError.message);
        } else if (response.success) {
          updateStatus('已启用静音');
        } else {
          updateStatus('静音失败: ' + response.error);
        }
      });
    } else {
      updateStatus('无法找到活动标签页');
    }
  });
});

document.getElementById('unmuteButton').addEventListener('click', () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) {
      chrome.tabs.sendMessage(tabs[0].id, { action: 'unmute' }, (response) => {
        if (chrome.runtime.lastError) {
          updateStatus('恢复失败: ' + chrome.runtime.lastError.message);
        } else if (response.success) {
          updateStatus('已恢复声音');
        } else {
          updateStatus('恢复失败: ' + response.error);
        }
      });
    } else {
      updateStatus('无法找到活动标签页');
    }
  });
});

document.getElementById('recordButton').addEventListener('click', () => {
  if (!isRecording) {
    chrome.runtime.sendMessage({ action: 'startRecording' }, (response) => {
      if (response && response.success) {
        isRecording = true;
        document.getElementById('recordButton').disabled = true;
        document.getElementById('stopRecordButton').disabled = false;
        updateStatus('录屏已开始');
      } else {
        updateStatus('录屏启动失败: ' + (response.error || '未知错误'));
      }
    });
  }
});

document.getElementById('stopRecordButton').addEventListener('click', () => {
  if (isRecording) {
    chrome.runtime.sendMessage({ action: 'stopRecording' }, (response) => {
      if (response && response.success) {
        isRecording = false;
        document.getElementById('recordButton').disabled = false;
        document.getElementById('stopRecordButton').disabled = true;
        updateStatus('录屏已停止');
      } else {
        updateStatus('录屏停止失败: ' + (response.error || '未知错误'));
      }
    });
  }
});

function updateStatus(message) {
  const statusDiv = document.getElementById('status');
  statusDiv.textContent = message;
  setTimeout(() => {
    statusDiv.textContent = '';
  }, 3000);
}