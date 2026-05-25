//! 桌面端入口。负责：
//! - 启动时拉起 Python 后端（uvicorn）作为子进程
//! - 退出时杀掉后端，避免残留
//!
//! 后端启动命令可通过环境变量覆盖：
//!   AFO_BACKEND_CMD   默认 "python"
//!   AFO_BACKEND_ARGS  默认 "-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8901"
//!   AFO_BACKEND_CWD   后端工作目录（默认应用资源目录的上一级）
//!   AFO_SKIP_BACKEND  设为 "1" 则不自动拉起（连已有后端时用）

use std::process::{Child, Command};
use std::sync::Mutex;

use tauri::{Manager, RunEvent};

/// 持有后端子进程句柄，退出时统一 kill。
struct BackendProcess(Mutex<Option<Child>>);

fn spawn_backend() -> Option<Child> {
    if std::env::var("AFO_SKIP_BACKEND").as_deref() == Ok("1") {
        println!("[afo] AFO_SKIP_BACKEND=1，跳过自动拉起后端");
        return None;
    }

    let cmd = std::env::var("AFO_BACKEND_CMD").unwrap_or_else(|_| "python".to_string());
    let args_str = std::env::var("AFO_BACKEND_ARGS").unwrap_or_else(|_| {
        "-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8901".to_string()
    });
    let args: Vec<&str> = args_str.split_whitespace().collect();

    let mut command = Command::new(&cmd);
    command.args(&args);
    if let Ok(cwd) = std::env::var("AFO_BACKEND_CWD") {
        command.current_dir(cwd);
    }

    match command.spawn() {
        Ok(child) => {
            println!("[afo] 后端已启动 pid={} ({} {})", child.id(), cmd, args_str);
            Some(child)
        }
        Err(e) => {
            eprintln!(
                "[afo] 启动后端失败: {e}。请确认已安装 Python 和依赖，\
                 或设置 AFO_SKIP_BACKEND=1 后手动启动后端。"
            );
            None
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let backend = spawn_backend();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(BackendProcess(Mutex::new(backend)))
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            // 应用退出时杀掉后端
            if let RunEvent::ExitRequested { .. } = event {
                if let Some(state) = app_handle.try_state::<BackendProcess>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(mut child) = guard.take() {
                            let _ = child.kill();
                            println!("[afo] 已停止后端进程");
                        }
                    }
                }
            }
        });
}
