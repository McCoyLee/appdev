# 桌面端（Tauri）构建与使用

把 Web 应用打包成 Windows/macOS/Linux 桌面应用。桌面端启动时会**自动拉起本地 Python 后端**，关闭时自动停掉，用户双击即用。

> ⚠️ 构建桌面端需要在**有图形界面的开发机**上做（Mac / Windows / Linux 桌面）。
> 纯无头服务器缺少 webkit2gtk + GUI，无法 build/运行——本仓库的 `src-tauri/` 源码就是为本地构建准备的。

---

## 它怎么工作

```
双击桌面 App
   │
   ├─ Tauri (Rust) 启动
   │    └─ spawn: python -m uvicorn backend.app.main:app --port 8901
   │         （随窗口关闭一起被 kill）
   │
   └─ WebView 加载前端 (frontend/dist)
        └─ 前端请求 127.0.0.1:8901
```

凭据仍走前端 localStorage（M3 已加 WebCrypto 加密）；后端依旧无状态。

---

## 一、前置依赖（开发机）

1. **Rust toolchain**

   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   # 重开终端后验证
   cargo --version
   ```

2. **Node ≥ 18**（构建前端用，前面已装则跳过）

3. **平台系统依赖**

   - **macOS**：`xcode-select --install`
   - **Windows**：安装 [Microsoft C++ Build Tools] + [WebView2 Runtime]（Win11 自带）
   - **Linux**：
     ```bash
     sudo apt install libwebkit2gtk-4.1-dev build-essential curl wget file \
       libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev
     ```

4. **Python 3.11 + 后端依赖**（桌面 App 运行时要拉起后端）

   ```bash
   pip install -r requirements.txt
   ```

---

## 二、准备图标（首次）

Tauri 需要多尺寸图标。准备一张 ≥1024×1024 的 PNG，然后：

```bash
cd src-tauri
npx @tauri-apps/cli icon path/to/your-logo.png
# 会自动生成 icons/ 下所有所需尺寸
```

（仓库里 `src-tauri/icons/` 是空的，build 前必须先跑这步，否则报缺图标。）

---

## 三、开发模式（热重载）

```bash
cd src-tauri
npm install          # 装 @tauri-apps/cli
npm run dev          # = tauri dev
```

`tauri dev` 会：

1. 跑 `frontend` 的 `npm run dev`（Vite :5173）
2. 编译 Rust 壳并打开窗口
3. 窗口里的前端连本地后端

> 后端：`tauri dev` 启动时 Rust 端会自动 spawn `python -m uvicorn ...`。
> 如果你想自己管后端（比如已经手动跑着），设 `AFO_SKIP_BACKEND=1`：
> ```bash
> AFO_SKIP_BACKEND=1 npm run dev
> ```

---

## 四、打包发行版

```bash
cd src-tauri
npm run build        # = tauri build
```

产物位置：

- **macOS**：`src-tauri/target/release/bundle/dmg/*.dmg` + `.app`
- **Windows**：`src-tauri/target/release/bundle/{msi,nsis}/*`
- **Linux**：`src-tauri/target/release/bundle/{deb,appimage}/*`

---

## 五、后端怎么打进安装包（两种策略）

桌面 App 运行时需要 Python 后端。两条路：

### 策略 A：要求用户机器有 Python（当前默认，简单）

- 安装包只含前端 + Rust 壳
- 启动时 `python -m uvicorn ...` 拉起后端
- **前提**：用户已装 Python 3.11 + `pip install -r requirements.txt`
- 适合：开发者、给懂点技术的人用

可用环境变量调整（在 App 启动环境或打包时配置）：

| 变量 | 默认 | 说明 |
|---|---|---|
| `AFO_BACKEND_CMD` | `python` | Python 可执行文件 |
| `AFO_BACKEND_ARGS` | `-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8901` | 启动参数 |
| `AFO_BACKEND_CWD` | （无） | 后端工作目录（需指到含 `backend/` 的目录） |
| `AFO_SKIP_BACKEND` | （无） | `=1` 时不自动拉起后端 |

### 策略 B：PyInstaller 打包后端成独立二进制（真·双击即用，进阶）

把后端冻结成单个可执行文件，作为 Tauri sidecar 一起打包，用户无需装 Python：

```bash
pip install pyinstaller
pyinstaller --onefile --name afo-backend \
  --collect-all nacl \
  --hidden-import uvicorn.logging \
  -p . \
  backend/app/main.py
# 产物 dist/afo-backend
```

然后：

1. 把 `dist/afo-backend` 拷到 `src-tauri/binaries/afo-backend-<target-triple>`
   （target triple 如 `x86_64-apple-darwin`，用 `rustc -Vv | grep host` 查）
2. `tauri.conf.json` 的 `bundle` 加 `externalBin: ["binaries/afo-backend"]`
3. `lib.rs` 改用 `tauri_plugin_shell` 的 sidecar API 启动它（而不是 `python -m`）

> PyInstaller 打包注意：PyNaCl 需要 `--collect-all nacl`；产物较大（~80MB）；
> macOS 要 code sign + notarize 才能免 Gatekeeper 警告。这部分留作后续工程化。

---

## 六、常见问题

**Q: build 报 "couldn't find icon"**
A: 先跑第二步 `tauri icon`。

**Q: Linux build 报缺 webkit2gtk**
A: 装第一步的系统依赖；Ubuntu 24.04 用 `4.1`，旧版用 `4.0`。

**Q: 双击 App 后白屏 / 连不上后端**
A: 多半是后端没起来。检查：是否装了 Python 依赖；`AFO_BACKEND_CWD` 是否指对；
   手动 `python -m uvicorn backend.app.main:app --port 8901` 能否跑通。

**Q: 国内编译拉 crates 慢**
A: 配 `~/.cargo/config.toml` 用国内镜像（如字节/中科大的 crates.io 镜像）。
