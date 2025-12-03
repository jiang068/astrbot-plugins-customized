"""漫画下载模块

负责从禁漫天堂下载漫画
"""
import asyncio

try:
    import jmcomic
except ImportError:
    jmcomic = None


class ComicDownloader:
    """漫画下载器"""
    
    def __init__(self, config_manager):
        """初始化下载器
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
    
    async def download_comic(self, comic_id: str, download_path: str):
        """下载漫画到指定目录
        
        Args:
            comic_id: 漫画ID
            download_path: 下载目录
        """
        # 动态读取配置
        proxy = self.config_manager.get_config_value('proxy', '')
        timeout = self.config_manager.get_config_value('timeout', 60)
        client_impl = self.config_manager.get_config_value('jm_client_impl', 'html')
        retry_times = self.config_manager.get_config_value('jm_retry_times', 5)
        download_cache = self.config_manager.get_config_value('download_cache', True)
        image_decode = self.config_manager.get_config_value('image_decode', True)
        image_suffix = self.config_manager.get_config_value('image_suffix', '')
        concurrent_images = self.config_manager.get_config_value('concurrent_images', 30)
        concurrent_photos = self.config_manager.get_config_value('concurrent_photos', 8)
        dir_rule = self.config_manager.get_config_value('dir_rule', 'Bd/Ptitle')
        normalize_zh = self.config_manager.get_config_value('normalize_zh', '')
        enable_jm_log = self.config_manager.get_config_value('enable_jm_log', False)
        jm_cookies_avs = self.config_manager.get_config_value('jm_cookies_avs', '')
        
        # 构建option配置字典
        option_dict = {
            'log': enable_jm_log,
            'dir_rule': {
                'base_dir': download_path,
                'rule': dir_rule,
            },
            'client': {
                'impl': client_impl,
                'retry_times': retry_times,
            },
            'download': {
                'cache': download_cache,
                'image': {
                    'decode': image_decode,
                },
                'threading': {
                    'image': concurrent_images,
                    'photo': concurrent_photos,
                }
            }
        }
        
        # 添加中文繁简转换配置
        if normalize_zh:
            option_dict['dir_rule']['normalize_zh'] = normalize_zh
        
        # 添加图片格式转换配置
        if image_suffix:
            option_dict['download']['image']['suffix'] = image_suffix
        
        # 设置代理和cookies
        postman_meta = {}
        if proxy:
            # 支持多种代理配置格式
            if proxy.lower() in ['system', 'clash', 'v2ray']:
                postman_meta['proxies'] = proxy.lower()
            else:
                postman_meta['proxies'] = {
                    'http': proxy,
                    'https': proxy
                }
        
        # 添加cookies配置
        if jm_cookies_avs:
            postman_meta['cookies'] = {
                'AVS': jm_cookies_avs
            }
        
        if postman_meta:
            option_dict['client']['postman'] = {
                'meta_data': postman_meta
            }
        
        # 设置超时
        if timeout and timeout != 60:  # 只有非默认值才设置
            if 'postman' not in option_dict['client']:
                option_dict['client']['postman'] = {'meta_data': {}}
            # JMComic 的超时配置需要在 postman 中设置
            option_dict['client']['postman']['timeout'] = timeout
        
        # 使用字典创建option
        option = jmcomic.JmModuleConfig.option_class().construct(option_dict)
        
        # 下载漫画（详细日志）
        self.config_manager.log('info', f"开始下载漫画 {comic_id}")
        self.config_manager.log('info', f"客户端类型: {client_impl}, 域名: 自动获取")
        self.config_manager.log('info', f"并发: 图片={concurrent_images}, 章节={concurrent_photos}")
        self.config_manager.log('info', f"下载目录: {download_path}")
        
        # 使用 asyncio.to_thread 在后台线程运行阻塞的下载函数
        # 这样不会阻塞 AstrBot 的事件循环
        await asyncio.to_thread(jmcomic.download_album, comic_id, option)
        # 下载完成由调用方记录关键日志
