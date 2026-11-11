# HIWIN RA6 ROS 2（Docker）

[English](README.md) | 繁體中文

用單一 Docker 映像檔，以 ROS 2 Humble 與 MoveIt 2 操作上銀 HIWIN RA6 機械手臂（預設型號 RA610-1476）。
主機上除了 Docker 之外不需要安裝任何東西。

支援型號：`ra605_710`、`ra610_1355`、`ra610_1476`、`ra610_1869`。

> 本文件是 [README.md](README.md) 的中文版，兩份內容保持同步；如有出入，以英文版為準。

## 1. 環境需求

- Ubuntu 22.04（或有 WSLg 的 WSL2），安裝 Docker Engine 與 `docker compose` 外掛
- Python 3（給 `run.py` 用，不需要額外套件）
- 要看 RViz：需要桌面環境（已設定 `DISPLAY`），或改用遠端桌面（第 2 節〈遠端桌面〉）從另一台電腦操作
- 實體手臂：手臂接在 HIWIN GC2 控制箱上，且能透過網路連到

## 2. 快速開始

```bash
git clone https://github.com/alianlbj23/hiwin_ros2.git
cd hiwin_ros2
./run.py
```

`run.py` 會顯示選單。第一次選 *Simulation* 或 *Real robot* 時，會詢問是否從 GitHub Container Registry
下載預先建好的映像檔（`ghcr.io/alianlbj23/hiwin_ros2:humble`，數 GB，只需下載一次）。
你的電腦上不需要編譯任何東西。

```
========== HIWIN RA6 Docker launcher ==========
 Settings: type=ra610_1476  IP=unset  RViz=true
  0) Settings (robot type / controller IP / RViz / domain ID / remote desktop)
  1) Simulation (mock hardware + RViz)
  2) Real robot (GC2 cabinet)
  3) Shell inside the container
  4) Pull / update the image (from GHCR)
  5) Follow container logs
  6) Status
  7) Stop containers
  8) Build the image locally (fallback)
  9) Remote desktop (VNC / browser / SSH)
  q) Quit
```

| 選項 | 功能 |
|---|---|
| 0 | 設定手臂型號、控制器 IP（含網路掃描與說明）、RViz 開關、ROS_DOMAIN_ID，以及（`6`）遠端桌面的密碼與連接埠。會存到 `.env`，下次自動沿用。 |
| 1 | 用模擬手臂啟動 MoveIt。在哪裡跑都安全，不需要實體手臂。有開 RViz 的話會跳出視窗。 |
| 2 | 連接實體手臂啟動 MoveIt。第一次會詢問控制器 IP，連線前會再請你確認一次。 |
| 3 | 開一個容器內的終端機，ROS 2 已經設定好。可以用來 `ros2 topic echo`、跑自己的節點等。 |
| 4 | 從 GHCR 下載最新映像檔（如果之前下載過桌面版，也會一併更新）。有新版本合併後再執行一次即可。 |
| 5 | 即時顯示執行中容器的 log。 |
| 6 | 顯示哪些容器在執行，以及映像檔是否存在。 |
| 7 | 停止全部容器。 |
| 8 | 改在本機建置映像檔（只有連不到 GHCR，或你在修改 Dockerfile 時才需要）。 |
| 9 | 在背景啟動遠端桌面：VNC、瀏覽器（noVNC）與 SSH 都在同一個容器裡。請見下方〈遠端桌面〉。 |

在選單中按 `Ctrl+C` 可以停止正在執行的模擬或實機。

要針對執行中的系統撰寫自己的 ROS 2 程式，請用第二個選單 `./dev.py`（第 4 節）。

### 模擬

1. `./run.py` → `1`
2. 按 Enter 沿用目前設定（或輸入 `n` 修改）。
3. 等 log 出現 `You can start planning now!`，RViz 會顯示手臂。
4. 在 RViz 拖曳末端的互動標記，然後在 MotionPlanning 面板按 **Plan & Execute**。

### 實體手臂

1. 確認 GC2 控制箱已開機、手臂在安全姿態，而且緊急停止按鈕伸手可及。
2. `./run.py` → `2`
3. 依提示選擇控制器 IP（只有第一次會問）。`run.py` 會掃描這台電腦所在的網段，找出在 HIWIN
   連接埠（TCP 1503）有回應的裝置並列為候選；`c` 手動輸入 IP，`s` 掃描你指定的網段，`h` 說明
   怎麼找 IP（教導盒、`ping`、`nc -zv <ip> 1503`）。在 WSL2 上自動偵測通常找不到，請用 `c` 或 `s`。
4. 閱讀警告後輸入 `y`。
5. 等出現 `You can start planning now!`。之後手臂會執行所有透過 MoveIt 送出的軌跡。

預設運動速度限制在手臂最大速度的 10%。請先在模擬中測試過，再到 RViz 調高（Velocity Scaling）。

### 遠端桌面（VNC / 瀏覽器 / SSH）

另一個映像檔 `ghcr.io/alianlbj23/hiwin_ros2:humble-desktop`，內容是同一套 ROS 2 環境，再加上
XFCE 桌面。可以從另一台電腦操作這台電腦，或用在沒有螢幕的機器上。

1. `./run.py` → `9`。第一次會下載桌面版映像檔並請你設定密碼（6–8 個字元：英文字母、數字或
   `. _ @ ! % + = -`）。密碼存在 `.env`，VNC、SSH 和 `sudo` 共用這組密碼。
2. `run.py` 會印出連線位址，用以下任一方式連線：

| 方式 | 位址 | 說明 |
|---|---|---|
| VNC Viewer（TigerVNC、RealVNC 等） | `<電腦 IP>:5901` | 只需要輸入密碼 |
| 瀏覽器（noVNC） | `http://<電腦 IP>:8080/vnc.html` | 不用安裝任何東西。按 *Connect* 後輸入密碼 |
| SSH | `ssh -p 2222 ros@<電腦 IP>` | 也可以用 VS Code *Remote-SSH* |

3. 在桌面上開終端機（或用 SSH 登入）。ROS 2、`/ros2_ws` 和 `ROS_DOMAIN_ID` 都已設定好，
   可以直接在裡面啟動：

```bash
ros2 launch hiwin_ra6_moveit_config ra6_moveit.launch.py ra_type:=$RA_TYPE use_fake_hardware:=true
# 實體手臂（注意事項與 ./run.py -> 2 相同）：
ros2 launch hiwin_ra6_moveit_config ra6_moveit.launch.py ra_type:=$RA_TYPE robot_ip:=$ROBOT_IP use_fake_hardware:=false
```

   RViz 會顯示在 VNC 桌面上（軟體 OpenGL 繪圖，顯示手臂模型足夠）。從 SSH 執行的指令，
   視窗也會出現在 VNC 桌面；想讓視窗顯示在自己的螢幕上，請改用 `ssh -X`。你也可以讓
   `./run.py` → `1`/`2` 繼續執行，桌面只拿來開 RViz、`ros2 topic` 或寫自己的程式，因為所有容器
   都在 host network 上。

4. 用 `./run.py` → `7` 停止。在 XFCE 裡登出只會重新開一個桌面工作階段，不會停止容器。

細節：

- 使用者是 `ros`（uid 1000）。`user_ws/` 掛載在 `/user_ws`，你在那裡編輯的程式碼就是主機上的檔案；
  `/home/ros` 裡的其他東西在容器停止後會消失。如果 `user_ws/build` 是由以 root 執行的 `dev`
  容器建立的，請先清掉（`./dev.py` → `5`）。
- 連接埠在 `./run.py` → `0` → `6` 修改。容器使用 host network，連接埠會開在這台電腦的所有網卡上，
  包括接手臂的那個網段，請設定夠強的密碼。SSH 不允許 root 登入。
- SSH 主機金鑰存在 Docker volume `hiwin_ros2_desktop_ssh_keys`，重新啟動後用戶端不會出現金鑰變更的警告。
- 畫面大小：在 `.env` 設定 `VNC_GEOMETRY=1920x1080`。noVNC 也可以縮放畫面（設定齒輪 → *Scaling mode*）。

## 3. 不用選單（docker compose）

```bash
docker pull ghcr.io/alianlbj23/hiwin_ros2:humble   # 第一次，以及每次發佈新版後
cp .env.example .env                     # 視需要修改 ROBOT_IP / RA_TYPE
xhost +local:root                        # 允許 RViz 開視窗

docker compose up sim                    # 模擬
docker compose up robot                  # 實體手臂
docker compose run --rm shell            # 容器內的終端機
docker compose up -d desktop             # 遠端桌面（.env 需要設定 VNC_PASSWORD）
docker compose down                      # 停止
```

`.env` 裡的設定：

| 變數 | 預設值 | 意義 |
|---|---|---|
| `RA_TYPE` | `ra610_1476` | 手臂型號 |
| `ROBOT_IP` | *（空白）* | GC2 控制器 IP，`robot` 必填 |
| `LAUNCH_RVIZ` | `true` | 是否開啟 RViz |
| `HIWIN_IMAGE` | `ghcr.io/alianlbj23/hiwin_ros2:humble` | `run.py` 與 compose 使用的映像檔。可以指向其他 GHCR tag（例如 `...:humble-<sha>`）。本機建置（`./run.py` → `8`、`docker compose build`）也會用同一個名稱，不需要修改。 |
| `ROS_DOMAIN_ID` | `0` | 要和其他想通訊的 ROS 2 機器一致 |
| `VNC_PASSWORD` | *（空白）* | 遠端桌面密碼（VNC、SSH 使用者 `ros`、sudo），6–8 個字元。沒設定的話 `desktop` 不會啟動。 |
| `VNC_PORT` / `NOVNC_PORT` / `SSH_PORT` | `5901` / `8080` / `2222` | 遠端桌面的連接埠 |
| `VNC_GEOMETRY` | `1920x1080` | 遠端桌面的畫面大小 |
| `VNC_DISPLAY` | `20` | 桌面容器內的 X display 編號。只有主機已經在用 `:20` 時才需要修改。 |
| `HIWIN_DESKTOP_IMAGE` | `ghcr.io/alianlbj23/hiwin_ros2:humble-desktop` | `desktop` 服務使用的映像檔 |

### 映像檔怎麼建置

[`.github/workflows/docker-image.yml`](.github/workflows/docker-image.yml) 會在每次 push 到 `main`
（以及手動 *Run workflow*）時建置 Dockerfile，並推送兩個 tag 到 GHCR：`humble`（永遠是最新的 `main`）
與 `humble-<short sha>`（固定不變，用來回復舊版）。合併後重新 pull `humble` 即可更新；只有修改
Dockerfile 時才需要在本機建置。

同一個 job 也會建置 Dockerfile 的 `desktop` target，推送為 `humble-desktop` 與
`humble-desktop-<short sha>`。單純執行 `docker build .` 產生的仍是不含桌面的映像檔；
`docker build --target desktop -t ghcr.io/alianlbj23/hiwin_ros2:humble-desktop .` 才會建置桌面版。
映像檔只發佈到 GHCR，不會推到 Docker Hub。

## 4. 撰寫自己的程式（`dev.py` + `user_ws/`）

`user_ws/` 是你的工作區。它以 bind mount 掛進另一個 `dev` 容器的 `/user_ws`，所以程式碼和建置結果
都留在你的電腦上；它會建置成預建 `/ros2_ws` 之上的 overlay，`/ros2_ws` 本身不會被修改。你的節點
透過 ROS 2（host network）和 MoveIt 溝通，就跟另一台電腦一樣。

```bash
./run.py   # → 1 啟動模擬（實體手臂選 2），讓它持續執行
./dev.py   # 在第二個終端機
```

```
========== HIWIN RA6 dev workspace ==========
 ROS_DOMAIN_ID=0  workspace=/path/to/hiwin_ros2/user_ws
  0) Settings (shared with run.py: ROS_DOMAIN_ID, robot type, ...)
  1) Shell in the dev container (/user_ws)
  2) Build user_ws (colcon build)
  3) Run a node from user_ws
  4) Test user_ws (colcon test)
  5) Clean build artefacts
  6) Status
  q) Quit
```

| 選項 | 功能 |
|---|---|
| 0 | 與 `run.py` 相同的設定選單（`ROS_DOMAIN_ID`、手臂型號、IP、RViz）。 |
| 1 | 開啟 dev 容器的 shell。會進到 `/user_ws`，ROS 2、`/ros2_ws` 以及（已建置的話）`/user_ws` 都已 source。 |
| 2 | 對 `user_ws/src` 全部執行 `colcon build --symlink-install`。用了 symlink-install，修改 Python 檔不需要重新建置。 |
| 3 | 從 `user_ws/src` 選一個套件和執行檔，可加參數，然後 `ros2 run`。如果 `user_ws/install` 不存在會先建置。 |
| 4 | `colcon test` + `colcon test-result --verbose`。 |
| 5 | 刪除 `user_ws/build install log`（在容器內刪，因為它們的擁有者是 root）。 |
| 6 | 顯示映像檔、`ROS_DOMAIN_ID`、`user_ws` 是否已建置、找到的套件與執行檔，以及執行中的容器。 |

`ROS_DOMAIN_ID` 是兩個選單共用的全域設定，存在 `.env`（任一選單的 `0`，或直接編輯檔案）：
sim/robot 容器和 dev 容器必須用同一個值；同一個網路上有兩支手臂或兩個人時，要用不同的值。

範本套件 `user_ws/src/hiwin_user_py` 示範一次完整的 MoveIt 2 往返。`move_demo` 讀取
`/joint_states`，透過 `/move_action` action 請 `move_group` 把一個關節移動 10°，再印出結果。
預設只做規劃；加上 `execute:=true` 才會真的動。

典型流程：

```bash
./dev.py → 2                                  # 建置
./dev.py → 3，選 move_demo                     # 只規劃，不會動
./dev.py → 3，額外參數：--ros-args -p execute:=true   # 手臂會動（模擬或實機）
./dev.py → 3，額外參數：--ros-args -p joint:=joint_2 -p delta_deg:=-5.0 -p execute:=true
./dev.py → 4                                  # 執行套件測試
```

#### `user_ws/` 的結構

| 路徑 | 內容 |
|---|---|
| `src/hiwin_user_py` | Python 範本套件（`move_demo`），複製一份開始寫自己的。 |
| `src/<your_pkg>` | 你另外加入的 ROS 2 套件。 |
| `.devrc` | dev 容器載入的 shell 檔：source ROS 2、`/ros2_ws` 與 `/user_ws`。 |
| `build/ install/ log/` | colcon 輸出。由容器建立（在主機上擁有者是 root），git 會忽略，用選項 `5` 刪除。 |

#### 新增自己的套件

1. 建在 `user_ws/src/` 底下（在 dev shell 執行 `ros2 pkg create --build-type ament_python my_pkg`，
   或複製 `hiwin_user_py`）。
2. 在 `setup.py` 的 `console_scripts` 註冊執行檔，`dev.py` 就會列出來。
3. 在 `package.xml` 加上 `moveit_msgs`、`control_msgs`、`sensor_msgs` 等相依。這些映像檔裡都已經有；
   需要映像檔裡沒有的套件，就加到 Dockerfile（第 3 節），讓 CI 重新建置映像檔。
4. `./dev.py` → `2`，再 `3`。

#### 不用選單的寫法

```bash
docker compose run --rm dev                                   # /user_ws 裡的 shell
docker compose run --rm dev bash -c "source /user_ws/.devrc && colcon build --symlink-install"
docker compose run --rm dev bash -c "source /user_ws/.devrc && colcon test && colcon test-result --verbose"
docker compose run --rm dev bash -c "source /user_ws/.devrc && ros2 run hiwin_user_py move_demo"
docker compose run --rm dev bash -c "source /user_ws/.devrc && ros2 run hiwin_user_py move_demo --ros-args -p execute:=true"
```

`.devrc` 依序 source ROS 2、`/ros2_ws/install`、`/user_ws/install`。因為都讀同一份 `.env`，dev 容器的
`ROS_DOMAIN_ID` 和 `sim`/`robot` 一致。傳給容器的指令裡不要寫 `${VAR}`：映像檔的 entrypoint 會在
bash 看到之前先把這類字串展開。

Humble 沒有 `moveit_py`，所以 Python 請直接使用 `moveit_msgs` 的 action 和 service（`/move_action`、
`/execute_trajectory`、`/compute_ik`、`/plan_kinematic_path`）。映像檔裡也有 C++ 的 `MoveGroupInterface`
（`moveit_ros_planning_interface`）可給 `ament_cmake` 套件使用；在 launch 檔中用
`MoveItConfigsBuilder("hiwin_ra6", package_name="hiwin_ra6_moveit_config")` 載入 MoveIt 設定。

限制：

- 容器以 root 執行，所以 `user_ws/build install log` 在主機上的擁有者是 root（用選項 `5` 從容器內刪除）。
- 在容器內 `apt install` 不會保留；程式需要的套件要加到 Dockerfile，讓 CI 重新建置映像檔。
- `user_ws` 中與 `/ros2_ws` 同名的套件會覆蓋後者，但只限 dev 容器內；`sim` 和 `robot` 不受影響。

## 5. 從自己的程式和手臂溝通

容器使用 host network，所以同一台電腦上（或同一個區網、相同 `ROS_DOMAIN_ID`）的任何 ROS 2 Humble
節點都能直接看到下列 topic，不需要額外設定。

在主機開第二個終端機試試看：

```bash
./dev.py            # → 1（dev 容器的 shell），或 ./run.py → 3
ros2 topic list
ros2 topic echo /joint_states
```

在發佈或呼叫任何東西之前，請先閱讀下一節：它標出了哪些介面會讓手臂移動。

規劃群組名稱：`manipulator`。關節名稱：`joint_1` … `joint_6`。
基座座標系：`base_link`。法蘭座標系：`link_6`。預設姿態名稱：`home`。

## 6. 系統執行時提供的介面

### ⚠ 會讓手臂移動的介面

以下全部由 `move_group` 與 `ros2_control` 提供。連接實體手臂時（`./run.py` → `2`），這些指令會立刻
讓真實硬體移動，沒有額外確認。請先在模擬中測試，並讓緊急停止按鈕保持在伸手可及之處。

| 介面 | 類型 | 會讓手臂移動嗎？ |
|---|---|---|
| `/move_action` | action `moveit_msgs/action/MoveGroup` | **會，除非** `planning_options.plan_only` 為 `true`。這個欄位預設是 `false`，所以沒特別設定的 goal 會規劃**並執行**。`move_demo` 預設會設成 `true`，除非你傳入 `execute:=true`。 |
| `/execute_trajectory` | action `moveit_msgs/action/ExecuteTrajectory` | **一定會。** 執行先前規劃好的軌跡（例如來自 `/plan_kinematic_path`）。 |
| `/manipulator_controller/follow_joint_trajectory` | action `control_msgs/action/FollowJointTrajectory` | **一定會。** 直接送給 `ros2_control`，**繞過 MoveIt 的碰撞檢查與速度縮放。** |
| `/manipulator_controller/joint_trajectory` | topic `trajectory_msgs/msg/JointTrajectory` | **一定會。** 同上，但送出就不管，沒有結果回饋。 |
| `/trajectory_execution_event` | topic `std_msgs/msg/String` | 不會。發佈 `stop` 會**中止** MoveIt 正在執行的軌跡（不影響直接送給控制器的軌跡）。 |
| `/plan_kinematic_path`、`/compute_cartesian_path`、`/compute_ik`、`/compute_fk`、`/check_state_validity`、`/get_planning_scene` | service | 不會。只做規劃與運動學計算，結果回傳給你，不會執行。 |
| `/planning_scene`、`/planning_scene_world`、`/collision_object`、`/attached_collision_object`、`/apply_planning_scene` | topic / service | 不會。它們改變 MoveIt 規劃時考慮的場景，本身不會移動任何東西。 |
| `/joint_states`、`/tf`、`/tf_static`、`/robot_description`、`/manipulator_controller/*state*`、`/monitored_planning_scene`、`/display_*`、`/motion_plan_request` | topic | 不會。唯讀狀態，可以放心訂閱。 |

下方表格中標示 **會移動** 的就是這四個介面。

### Topics

| Topic | 類型 | 內容 |
|---|---|---|
| `/joint_states` | `sensor_msgs/msg/JointState` | 目前的關節位置與速度，500 Hz |
| `/tf`、`/tf_static` | `tf2_msgs/msg/TFMessage` | 座標轉換樹 `base_link` → `link_1` … `link_6` |
| `/robot_description` | `std_msgs/msg/String` | 手臂 URDF（latched） |
| `/manipulator_controller/controller_state` | `control_msgs/msg/JointTrajectoryControllerState` | 軌跡執行中的期望與實際關節狀態 |
| `/manipulator_controller/joint_trajectory` | `trajectory_msgs/msg/JointTrajectory` | **會移動。** 發佈到這裡會把軌跡直接送給控制器，繞過 MoveIt（沒有碰撞檢查、沒有結果） |
| `/manipulator_controller/state` | `control_msgs/msg/JointTrajectoryControllerState` | 控制器狀態（Humble 的名稱；`controller_state` 是較新的別名） |
| `/dynamic_joint_states` | `control_msgs/msg/DynamicJointState` | 與 `/joint_states` 相同的資料，附介面名稱 |
| `/monitored_planning_scene` | `moveit_msgs/msg/PlanningScene` | MoveIt 目前的場景，每次變更時發佈 |
| `/planning_scene` | `moveit_msgs/msg/PlanningScene` | 發佈到這裡修改場景 |
| `/planning_scene_world` | `moveit_msgs/msg/PlanningSceneWorld` | 發佈到這裡加入環境物件 |
| `/collision_object` | `moveit_msgs/msg/CollisionObject` | 發佈到這裡新增或移除障礙物 |
| `/attached_collision_object` | `moveit_msgs/msg/AttachedCollisionObject` | 發佈到這裡把物件附著到手臂上 |
| `/display_planned_path` | `moveit_msgs/msg/DisplayTrajectory` | 最近一次規劃的軌跡（顯示在 RViz） |
| `/motion_plan_request` | `moveit_msgs/msg/MotionPlanRequest` | 最近一次規劃請求 |
| `/trajectory_execution_event` | `std_msgs/msg/String` | 發佈 `stop` 以中止 MoveIt 正在執行的軌跡 |
| `/display_contacts` | `visualization_msgs/msg/MarkerArray` | RViz 用的碰撞接觸點標記 |

### Actions

| Action | 類型 | 用途 |
|---|---|---|
| `/move_action` | `moveit_msgs/action/MoveGroup` | **會移動，除非 `planning_options.plan_only=true`。** 規劃並執行一段有碰撞檢查的動作。MoveIt 用戶端的主要入口，`move_demo` 使用這個。 |
| `/execute_trajectory` | `moveit_msgs/action/ExecuteTrajectory` | **會移動。** 執行已規劃好的軌跡 |
| `/manipulator_controller/follow_joint_trajectory` | `control_msgs/action/FollowJointTrajectory` | **會移動。** 直接把關節軌跡送給控制器，繞過 MoveIt |

### Services

| Service | 類型 | 用途 |
|---|---|---|
| `/plan_kinematic_path` | `moveit_msgs/srv/GetMotionPlan` | 只規劃，回傳軌跡 |
| `/compute_ik` | `moveit_msgs/srv/GetPositionIK` | 逆向運動學 |
| `/compute_fk` | `moveit_msgs/srv/GetPositionFK` | 順向運動學 |
| `/compute_cartesian_path` | `moveit_msgs/srv/GetCartesianPath` | 經過指定路徑點的直線笛卡兒路徑 |
| `/get_planning_scene` | `moveit_msgs/srv/GetPlanningScene` | 讀取目前場景與手臂狀態 |
| `/check_state_validity` | `moveit_msgs/srv/GetStateValidity` | 檢查某個手臂狀態是否碰撞或違反限制 |
| `/get_planner_params`、`/set_planner_params` | `moveit_msgs/srv/GetPlannerParams`、`SetPlannerParams` | 執行中讀取或調整規劃器參數 |
| `/manipulator_controller/query_state` | `control_msgs/srv/QueryTrajectoryState` | 詢問控制器某個時間點的規劃狀態 |
| `/apply_planning_scene` | `moveit_msgs/srv/ApplyPlanningScene` | 修改場景並等待套用完成 |
| `/query_planner_interface` | `moveit_msgs/srv/QueryPlannerInterfaces` | 列出可用的規劃器（`ompl`、`chomp`、`pilz_industrial_motion_planner`） |
| `/controller_manager/list_controllers` | `controller_manager_msgs/srv/ListControllers` | 確認 `joint_state_broadcaster` 和 `manipulator_controller` 是 `active` |

## 7. 確認系統正常運作

在容器的 shell 裡（`./dev.py` → `1` 或 `./run.py` → `3`）：

```bash
ros2 control list_controllers
# joint_state_broadcaster  ... active
# manipulator_controller   ... active

ros2 topic hz /joint_states          # 約 500 Hz
ros2 action list                     # /move_action, /execute_trajectory, ...
```

## 8. 疑難排解

| 症狀 | 處理方式 |
|---|---|
| RViz 視窗沒出現 | 在主機執行 `xhost +local:root`，並確認已設定 `DISPLAY`。或在設定中把 RViz 設為 `false`，只用 topic。 |
| `ros2 node list` 只列出少數節點 | 執行 `ros2 node list --no-daemon`，或 `ros2 daemon stop` 後再試一次。 |
| 實體手臂：連不上 | `./run.py` → `0` → `2` 重新掃描；正常的控制器會顯示 "port 1503 answers"。否則從主機執行 `ping <ip>` 和 `nc -zv <ip> 1503`，並確認控制箱已開機且處於接受外部控制的模式。 |
| 控制器沒有出現在候選清單 | 它所在的網段這台電腦不會自動掃描（大於 /24，或在 WSL2 NAT 後面）。用 `s` 指定區網網段（例如 `192.168.0.0/24`），或用 `c` 輸入 IP。 |
| log 出現 `No 3D sensor plugin(s) defined for octomap updates` | 無害，只是表示沒有設定深度相機。 |
| 啟動失敗，找不到映像檔 | `./run.py` → `4` 下載。 |
| 遠端桌面：容器一啟動就停止 | `./run.py` → `5` 看原因：通常是沒有設定 `VNC_PASSWORD`，或連接埠已被這台電腦的其他程式占用。 |
| 遠端桌面：從其他電腦連不進來 | 確認防火牆有開放這些連接埠（Ubuntu：`sudo ufw allow 5901,8080,2222/tcp`）。在 WSL2 上連接埠只開在 WSL 的 VM 上；請在 Windows 本機用 `localhost` 連，或把連接埠轉發到區網。 |
| Docker Desktop 上的遠端桌面：完全沒回應，連 `localhost` 都不行 | Docker Desktop 的 `network_mode: host` 只存在它自己的 VM 裡。請開啟 *Settings → Resources → Network → Enable host networking*（需要 Docker Desktop 4.34 以上），然後重新啟動容器。這也會影響 `sim`/`robot`（ROS 2 的節點探索）。 |
| `docker pull` 被拒絕 / unauthorized | GHCR 套件是私有的。把它改成公開（GitHub → Packages → hiwin_ros2 → Package settings → Change visibility），或用有 `read:packages` 權限的 token 執行 `docker login ghcr.io`。 |

## 授權

請見 [LICENSE](LICENSE)。基於 [HIWINCorporation/hiwin_ros2](https://github.com/HIWINCorporation/hiwin_ros2)。
