// 阻止 Windows 上多弹一个控制台窗口
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    app_for_oneself_lib::run()
}
