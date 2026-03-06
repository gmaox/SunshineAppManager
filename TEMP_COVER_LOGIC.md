# 封面文件处理流程更新说明

## 修改内容

当前已实现将封面文件先写入到 temp 目录，然后在保存 apps.json 时一起写入到目标目录的逻辑。

### 流程说明

1. **生成新增游戏封面** (`generate_covers_for_entries`)
   - 所有封面文件先写入到：`{脚本目录}/temp/`
   - 包括从 Steam 本地副本复制的封面 (`try_set_steam_cover_for_shortcut`)
   - 包括从应用图标生成的封面 (`create_image_with_icon`)

2. **导入自定义封面** (`confirm_add_window._on_import_cover`)
   - 所有自定义导入的封面先写入到：`{脚本目录}/temp/`

3. **更换已有游戏封面** (`manage_games.on_change_cover`)
   - 所有更换的封面先写入到：`{脚本目录}/temp/`

4. **保存 apps.json** (`basic_def.save_apps_json`)
   - 保存 apps.json 文件
   - 自动检查 temp 目录，将所有文件复制到目标：`{APP_INSTALL_PATH}/config/covers/`
   - 清空 temp 目录

### 文件路径

- **临时存储路径**：`{脚本目录}/temp/`
  - `output_image{N}.png` - 自动生成的封面
  - `custom_{UUID}.jpg` - 用户导入的自定义封面

- **最终目标路径**：`{APP_INSTALL_PATH}/config/covers/`
  - 相同的文件名

### 改动文件

1. **basic_def.py**
   - 添加全局变量 `SCRIPT_DIR` 和 `TEMP_COVERS_DIR`
   - `generate_covers_for_entries()` - 改为使用 `TEMP_COVERS_DIR`
   - `save_apps_json()` - 改为使用 `TEMP_COVERS_DIR` 处理 temp 文件迁移
   - `_process_confirm_add_entries()` - 移除重复的 temp 处理代码

2. **confirm_add_window.py**
   - 导入 `TEMP_COVERS_DIR`
   - `_on_import_cover()` - 改为使用 `TEMP_COVERS_DIR`

3. **manage_games.py**
   - 导入 `TEMP_COVERS_DIR`
   - `on_change_cover()` - 改为使用 `TEMP_COVERS_DIR`

### 注意事项

- 所有对 `save_apps_json()` 的调用会自动处理 temp 文件的迁移
- 无需在调用处额外处理 temp 文件
- temp 文件夹位于脚本目录下，使用后自动清空
- 覆盖目标目录会在保存时自动创建
