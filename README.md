# AstrBot JM2PDF 插件

下载禁漫天堂（JMComic）漫画并自动转换为 PDF 发送给用户。

## 功能特点

-  简单易用：`/jm <漫画ID>` 即可下载并转换
-  无损转换：使用 img2pdf 进行无损 PDF 转换
-  异步处理：不阻塞其他插件运行
-  任务队列：多用户自动排队，避免资源耗尽
-  超时保护：超时后转换部分内容，避免无限等待
-  内存优化：默认配置约 50-150MB/用户

## 快速开始

### 1. 安装依赖

**使用 pip（推荐）：**
```bash
pip install jmcomic img2pdf
```

**使用 uv（快速）：**
```bash
pip install uv
uv pip install jmcomic img2pdf
```

**使用 Poetry：**
```bash
poetry add jmcomic img2pdf
```

**使用 Docker：**
```dockerfile
RUN pip install jmcomic img2pdf
```

### 2. 安装插件

在astrbot网页控制台安装此插件zip，或直接放入plugins目录中。

## 使用方法

```
/jm 123456
```
这里的“/”是你的astrbot的唤醒词，默认是“/”，当然你可能已经改成其他的了。

## 核心配置

### 主要配置项

| 配置项 | 默认值 | 说明 |
|--------|-------|------|
| `concurrent_images` | 8 | 同时下载的图片数 |
| `concurrent_photos` | 2 | 同时下载的章节数 |
| `max_concurrent_tasks` | 2 | 最大并发用户数 |
| `task_timeout_minutes` | 10 | 任务超时时间 |
| `keep_pdf` | false | 是否缓存PDF |

### 白名单

```json
{
  "whitelist_groups": "123,456",  // 群组ID，留空=全部
  "whitelist_users": "111,222"    // 用户ID，留空=全部
}
```

## 许可证

MIT License
