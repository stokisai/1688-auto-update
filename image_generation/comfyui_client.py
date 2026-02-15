"""
ComfyUI Flux Kontext 图生图客户端

通过ComfyUI API进行图生图处理，支持动态工作流配置。
"""

import json
import os
import time
import random
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urljoin
import urllib3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ComfyUIFluxKontextClient:
    """ComfyUI Flux Kontext 图生图客户端"""
    
    # 默认工作流模板
    DEFAULT_WORKFLOW = {
        "39": {"inputs": {"vae_name": "ae.safetensors"}, "class_type": "VAELoader"},
        "42": {"inputs": {"image": ["142", 0]}, "class_type": "FluxKontextImageScale"},
        "124": {"inputs": {"pixels": ["42", 0], "vae": ["39", 0]}, "class_type": "VAEEncode"},
        "31": {
            "inputs": {
                "seed": 0,
                "steps": 20,
                "cfg": 1,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1,
                "model": ["37", 0],
                "positive": ["35", 0],
                "negative": ["135", 0],
                "latent_image": ["124", 0]
            },
            "class_type": "KSampler"
        },
        "135": {"inputs": {"conditioning": ["6", 0]}, "class_type": "ConditioningZeroOut"},
        "35": {"inputs": {"guidance": 2.5, "conditioning": ["177", 0]}, "class_type": "FluxGuidance"},
        "177": {"inputs": {"conditioning": ["6", 0], "latent": ["124", 0]}, "class_type": "ReferenceLatent"},
        "38": {
            "inputs": {
                "clip_name1": "clip_l.safetensors",
                "clip_name2": "t5xxl_fp8_e4m3fn_scaled.safetensors",
                "type": "flux",
                "device": "default"
            },
            "class_type": "DualCLIPLoader"
        },
        "6": {"inputs": {"text": "", "clip": ["38", 0]}, "class_type": "CLIPTextEncode"},
        "37": {"inputs": {"unet_name": "flux1-dev-kontext_fp8_scaled.safetensors", "weight_dtype": "default"}, "class_type": "UNETLoader"},
        "278": {"inputs": {"images": ["277", 1]}, "class_type": "PreviewImage"},
        "8": {"inputs": {"samples": ["31", 0], "vae": ["39", 0]}, "class_type": "VAEDecode"},
        "277": {
            "inputs": {
                "model_name": "4x-UltraSharp.pth",
                "rescale_after_model": True,
                "rescale_method": "nearest-exact",
                "rescale": "by percentage",
                "percent": 50,
                "width": 1024,
                "height": 1024,
                "longer_side": 1024,
                "crop": "disabled",
                "image_output": "Preview",
                "link_id": 0,
                "save_prefix": "ComfyUI",
                "image": ["8", 0],
                "vae": ["39", 0]
            },
            "class_type": "easy hiresFix"
        },
        "142": {"inputs": {"image": "", "upload": "image"}, "class_type": "LoadImage"}
    }
    
    def __init__(self, server_url: str = ""):
        """
        初始化ComfyUI客户端
        
        Args:
            server_url: ComfyUI服务器地址 (如 https://xxx:port)
        """
        self.server_url = server_url.rstrip('/') if server_url else ""
        self.session = requests.Session()
        self.session.verify = False  # 禁用SSL验证（自签名证书）
        # 默认不读取系统代理，避免内网/反代 ComfyUI 被本机代理劫持导致 ProxyError
        # 如确需走系统代理，可设置环境变量 COMFYUI_USE_SYSTEM_PROXY=1
        self.session.trust_env = os.getenv("COMFYUI_USE_SYSTEM_PROXY", "0") == "1"
        
        # 工作流配置
        self.workflow_template = None
        self.prompt_node_id = "6"
        self.prompt_param_path = "inputs.text"
        self.image_node_id = "142"
        self.image_param_path = "inputs.image"
        self.output_node_id = "278"
        
    def set_server_url(self, url: str):
        """设置服务器地址"""
        self.server_url = url.rstrip('/') if url else ""

    @staticmethod
    def _normalize_workflow_json(workflow_json: dict) -> dict:
        """
        兼容两种工作流格式：
        1) API prompt 格式: {"6": {"class_type": "...", "inputs": {...}}, ...}
        2) 前端 workflow 格式: {"nodes": [...], "links": [...], ...}
        """
        if not isinstance(workflow_json, dict):
            return workflow_json

        # 已是 API 格式
        if workflow_json and all(
            isinstance(v, dict) and "class_type" in v and isinstance(v.get("inputs", {}), dict)
            for v in workflow_json.values()
            if isinstance(v, dict)
        ):
            return workflow_json

        nodes = workflow_json.get("nodes")
        if not isinstance(nodes, list):
            return workflow_json

        links = workflow_json.get("links", [])
        link_map = {}
        if isinstance(links, list):
            for item in links:
                if isinstance(item, list) and len(item) >= 5:
                    # [link_id, from_node, from_slot, to_node, to_slot, type]
                    link_map[item[0]] = item

        def _is_int_like(value: Any) -> bool:
            if isinstance(value, bool):
                return False
            if isinstance(value, int):
                return True
            if isinstance(value, str):
                s = value.strip()
                return s.lstrip("-").isdigit()
            return False

        def _is_float_like(value: Any) -> bool:
            if isinstance(value, bool):
                return False
            if isinstance(value, (int, float)):
                return True
            if isinstance(value, str):
                s = value.strip()
                try:
                    float(s)
                    return True
                except Exception:
                    return False
            return False

        def _matches_expected_type(value: Any, expected_type: str) -> bool:
            t = (expected_type or "").upper()
            if t == "INT":
                return _is_int_like(value)
            if t == "FLOAT":
                return _is_float_like(value)
            if t == "BOOLEAN":
                return isinstance(value, bool)
            if t in ("STRING", "COMBO"):
                return isinstance(value, str)
            return True

        def _coerce_widget_value(value: Any, expected_type: str) -> Any:
            t = (expected_type or "").upper()
            if t == "INT":
                if _is_int_like(value):
                    return int(str(value).strip())
                return value
            if t == "FLOAT":
                if _is_float_like(value):
                    return float(str(value).strip())
                return value
            if t == "BOOLEAN":
                if isinstance(value, bool):
                    return value
                return value
            return value

        api_prompt = {}
        for node in nodes:
            if not isinstance(node, dict):
                continue

            node_id = node.get("id")
            class_type = node.get("type")
            if node_id is None or not class_type:
                continue

            api_inputs = {}
            inputs_schema = node.get("inputs", [])
            widgets_values = node.get("widgets_values", []) or []
            widget_index = 0

            if not isinstance(inputs_schema, list):
                inputs_schema = []

            for input_item in inputs_schema:
                if not isinstance(input_item, dict):
                    continue
                name = input_item.get("name")
                if not name:
                    continue

                link_id = input_item.get("link")
                if link_id is not None and link_id in link_map:
                    link = link_map[link_id]
                    from_node = str(link[1])
                    from_slot = link[2]
                    api_inputs[name] = [from_node, from_slot]
                    continue

                # 无连接时尝试从 widgets_values 取默认值（按出现顺序）
                if "widget" in input_item:
                    expected_type = input_item.get("type", "")
                    chosen_idx = None

                    # 优先找类型匹配的值，避免 KSampler 等节点出现 widgets_values 偏移
                    for idx in range(widget_index, len(widgets_values)):
                        if _matches_expected_type(widgets_values[idx], expected_type):
                            chosen_idx = idx
                            break

                    # 若没找到匹配值，回退到当前索引（保持原有兼容）
                    if chosen_idx is None and widget_index < len(widgets_values):
                        chosen_idx = widget_index

                    if chosen_idx is not None:
                        api_inputs[name] = _coerce_widget_value(widgets_values[chosen_idx], expected_type)
                        widget_index = chosen_idx + 1

            api_prompt[str(node_id)] = {
                "inputs": api_inputs,
                "class_type": class_type,
            }

        return api_prompt if api_prompt else workflow_json

    @staticmethod
    def _repair_ksampler_inputs(workflow_json: dict) -> dict:
        """
        修复常见 KSampler 参数错位问题（历史前端工作流转换导致）。
        """
        if not isinstance(workflow_json, dict):
            return workflow_json

        def _int_like(v: Any) -> Optional[int]:
            if isinstance(v, bool):
                return None
            if isinstance(v, int):
                return v
            if isinstance(v, str) and v.strip().lstrip("-").isdigit():
                try:
                    return int(v.strip())
                except Exception:
                    return None
            return None

        def _float_like(v: Any) -> Optional[float]:
            if isinstance(v, bool):
                return None
            if isinstance(v, (int, float)):
                return float(v)
            if isinstance(v, str):
                try:
                    return float(v.strip())
                except Exception:
                    return None
            return None

        for _, node_data in workflow_json.items():
            if not isinstance(node_data, dict):
                continue
            if node_data.get("class_type") != "KSampler":
                continue

            inputs = node_data.get("inputs", {})
            if not isinstance(inputs, dict):
                continue

            steps = inputs.get("steps")
            cfg = inputs.get("cfg")
            sampler_name = inputs.get("sampler_name")
            scheduler = inputs.get("scheduler")
            denoise = inputs.get("denoise")

            # 典型错位模式：
            # steps='randomize', cfg=9, sampler_name=1, scheduler='res_multistep', denoise='simple'
            if (
                isinstance(steps, str)
                and _float_like(cfg) is not None
                and _float_like(sampler_name) is not None
                and isinstance(scheduler, str)
                and isinstance(denoise, str)
            ):
                fixed_steps = _int_like(cfg)
                fixed_cfg = _float_like(sampler_name)
                if fixed_steps is not None:
                    inputs["steps"] = fixed_steps
                if fixed_cfg is not None:
                    inputs["cfg"] = fixed_cfg
                inputs["sampler_name"] = scheduler
                inputs["scheduler"] = denoise
                inputs["denoise"] = 1.0

            # 基础兜底，避免提交前类型非法
            if _int_like(inputs.get("steps")) is None:
                inputs["steps"] = 20
            else:
                inputs["steps"] = _int_like(inputs.get("steps"))

            if _float_like(inputs.get("cfg")) is None:
                inputs["cfg"] = 1.0
            else:
                inputs["cfg"] = _float_like(inputs.get("cfg"))

            if _float_like(inputs.get("denoise")) is None:
                inputs["denoise"] = 1.0
            else:
                inputs["denoise"] = _float_like(inputs.get("denoise"))

            if not isinstance(inputs.get("sampler_name"), str):
                inputs["sampler_name"] = "euler"
            if not isinstance(inputs.get("scheduler"), str):
                inputs["scheduler"] = "simple"

        return workflow_json
        
    def set_workflow(self, workflow_json: dict, prompt_node_id: str = "6",
                     prompt_param_path: str = "inputs.text",
                     image_node_id: str = None, image_param_path: str = None):
        """
        设置自定义工作流

        Args:
            workflow_json: 工作流JSON
            prompt_node_id: 提示词节点ID
            prompt_param_path: 提示词参数路径
            image_node_id: 图片输入节点ID（可选）
            image_param_path: 图片参数路径（可选）
        """
        normalized_workflow = self._normalize_workflow_json(workflow_json)
        normalized_workflow = self._repair_ksampler_inputs(normalized_workflow)
        self.workflow_template = normalized_workflow
        self.prompt_node_id = prompt_node_id
        self.prompt_param_path = prompt_param_path

        # 自动检测输出节点（SaveImage / PreviewImage）
        self.output_node_id = self._auto_detect_output_node(normalized_workflow)

        # 如果提供了图片节点配置，使用它
        if image_node_id:
            self.image_node_id = image_node_id
            self.image_param_path = image_param_path or "inputs.image"
        else:
            # 没有提供图片节点，尝试自动检测
            detected_image_node = self._auto_detect_image_node(normalized_workflow)
            if detected_image_node:
                self.image_node_id = detected_image_node[0]
                self.image_param_path = detected_image_node[1]
                print(f"  [工作流] 自动检测到图片节点: {self.image_node_id} ({self.image_param_path})")
            else:
                # 没有检测到图片节点，设置为 None 以跳过图片设置
                self.image_node_id = None
                self.image_param_path = None
                print(f"  [工作流] 警告: 未检测到图片输入节点，将跳过图片设置")

    def _auto_detect_output_node(self, workflow_json: dict) -> str:
        """自动检测工作流中的输出节点（SaveImage / PreviewImage）"""
        output_classes = {"SaveImage", "PreviewImage", "SaveImageWebsocket"}
        # 优先 SaveImage，其次 PreviewImage
        save_nodes = []
        preview_nodes = []
        for node_id, node in workflow_json.items():
            if not isinstance(node, dict):
                continue
            cls = node.get("class_type", "")
            if cls == "SaveImage":
                save_nodes.append(node_id)
            elif cls in output_classes:
                preview_nodes.append(node_id)
        if save_nodes:
            chosen = save_nodes[-1]
            print(f"  [工作流] 自动检测到输出节点: {chosen} (SaveImage)")
            return chosen
        if preview_nodes:
            chosen = preview_nodes[-1]
            print(f"  [工作流] 自动检测到输出节点: {chosen} (Preview)")
            return chosen
        print(f"  [工作流] 未检测到输出节点，使用默认: {self.output_node_id}")
        return self.output_node_id

    def _auto_detect_image_node(self, workflow_json: dict) -> tuple:
        """自动检测工作流中的图片输入节点"""
        candidate_keys = [
            "image", "images", "image_path", "input_image",
            "source_image", "init_image", "reference_image"
        ]

        def _first_image_key(inputs: dict):
            for key in candidate_keys:
                if key in inputs:
                    return key
            return None

        def _first_image_like_key(inputs: dict):
            exact = _first_image_key(inputs)
            if exact:
                return exact
            for key in inputs.keys():
                key_l = str(key).lower()
                if key_l in ("image_output", "filename_prefix"):
                    continue
                if any(token in key_l for token in ("image", "img", "pixels", "source", "reference", "init")):
                    return key
            return None

        def _looks_like_image_input_node(class_type: str, inputs: dict) -> bool:
            cls = (class_type or "").lower()
            if cls in ("loadimage", "loadimageoutput", "loadimagefromoutput", "loadimagefromoutputs"):
                return True
            if any(token in cls for token in ("loadimage", "imageinput", "imageloader", "inputimage")):
                return True
            if "image" in cls and any(token in cls for token in ("load", "input", "output", "reference", "reader")):
                return True
            if inputs.get("upload") == "image":
                return True
            return False

        # 查找常见图片输入节点
        for node_id, node_data in workflow_json.items():
            if isinstance(node_data, dict):
                class_type = node_data.get("class_type", "")
                inputs = node_data.get("inputs", {})
                if _looks_like_image_input_node(class_type, inputs):
                    key = _first_image_like_key(inputs) or "image"
                    return (node_id, f"inputs.{key}")

        # 查找其他可能的图片输入节点
        for node_id, node_data in workflow_json.items():
            if isinstance(node_data, dict):
                class_type = node_data.get("class_type", "")
                if any(token in class_type for token in ["LoadImage", "ImageInput", "ImageLoader", "InputImage"]):
                    inputs = node_data.get("inputs", {})
                    key = _first_image_like_key(inputs)
                    if key:
                        return (node_id, f"inputs.{key}")

        # 带 upload=image 标识
        for node_id, node_data in workflow_json.items():
            if isinstance(node_data, dict):
                inputs = node_data.get("inputs", {})
                if inputs.get("upload") == "image":
                    key = _first_image_like_key(inputs) or "image"
                    return (node_id, f"inputs.{key}")

        # 最后兜底：任何带图片语义输入字段的节点（排除输出/保存）
        for node_id, node_data in workflow_json.items():
            if not isinstance(node_data, dict):
                continue
            class_type = (node_data.get("class_type", "") or "").lower()
            if "save" in class_type or "preview" in class_type:
                continue
            inputs = node_data.get("inputs", {})
            if not isinstance(inputs, dict):
                continue
            key = _first_image_like_key(inputs)
            if key:
                return (node_id, f"inputs.{key}")

        return None
        
    def test_connection(self) -> bool:
        """
        测试服务器连接
        
        Returns:
            是否连接成功
        """
        if not self.server_url:
            return False
            
        try:
            url = urljoin(self.server_url, "/system_stats")
            response = self.session.get(url, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def upload_image(self, image_path: str) -> str:
        """
        上传图片到服务器
        
        Args:
            image_path: 本地图片路径
            
        Returns:
            上传后的文件名
        """
        if not self.server_url:
            raise ValueError("未配置ComfyUI服务器地址")
            
        url = urljoin(self.server_url, "/upload/image")
        
        with open(image_path, 'rb') as f:
            files = {'image': (Path(image_path).name, f)}
            response = self.session.post(url, files=files, timeout=60)
            
        response.raise_for_status()
        result = response.json()
        
        return result.get('name', '')
    
    def image_to_image(self, source_image: str, prompt: str = None,
                       seed: int = None, steps: int = 20,
                       guidance: float = 2.5, output_dir: str = "./output/generated") -> str:
        """
        使用Flux Kontext进行图生图处理
        
        Args:
            source_image: 本地图片路径
            prompt: 提示词 (可选，不传则为洗稿模式)
            seed: 随机种子
            steps: 采样步数
            guidance: 引导强度
            output_dir: 输出目录
            
        Returns:
            生成图片的本地保存路径
        """
        if not self.server_url:
            raise ValueError("未配置ComfyUI服务器地址")
        
        # 确保输出目录存在
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 1. 上传图片
        print(f"[1/5] 上传图片...")
        image_name = self.upload_image(source_image)
        print(f"  上传成功: {image_name}")
        
        # 2. 构建工作流
        print(f"[2/5] 构建工作流...")
        workflow = self._build_workflow(
            image_name=image_name,
            prompt=prompt,  # 保持 None，让 _build_workflow 决定是否设置
            seed=seed if seed is not None else random.randint(0, 999999999999999),
            steps=steps,
            guidance=guidance
        )
        
        # 3. 提交工作流
        print(f"[3/5] 提交工作流...")
        prompt_id = self._submit_workflow(workflow)
        print(f"  提交成功, prompt_id: {prompt_id}")
        
        # 4. 等待结果
        print(f"[4/5] 等待生成完成...")
        result_info = self.wait_for_result(prompt_id)
        output_filename = result_info.get("filename", "")
        result_subfolder = result_info.get("subfolder", "")
        result_type = result_info.get("type", "output")
        print(f"  生成成功! filename={output_filename}, type={result_type}")

        # 5. 下载图片
        print(f"[5/5] 下载生成的图片...")
        output_path = Path(output_dir) / f"generated_{int(time.time())}.png"
        self.download_result(output_filename, str(output_path),
                             subfolder=result_subfolder, file_type=result_type)
        print(f"  下载完成: {output_path}")
        
        return str(output_path)
    
    def _build_workflow(self, image_name: str, prompt: str,
                        seed: int, steps: int, guidance: float) -> dict:
        """构建工作流JSON"""
        # 使用自定义工作流或默认工作流
        template = self.workflow_template or self.DEFAULT_WORKFLOW

        # 深拷贝
        workflow = json.loads(json.dumps(template))

        def _set_nested_value(node: dict, param_path: str, value: Any) -> bool:
            try:
                parts = param_path.split(".")
                target = node
                for part in parts[:-1]:
                    if part not in target:
                        target[part] = {}
                    if not isinstance(target[part], dict):
                        return False
                    target = target[part]
                last_key = parts[-1]
                target[last_key] = value
                return True
            except Exception:
                return False

        candidate_keys = [
            "image", "images", "image_path", "input_image",
            "source_image", "init_image", "reference_image"
        ]

        def _pick_image_key(inputs: dict) -> str:
            if not isinstance(inputs, dict):
                return "image"
            for key in candidate_keys:
                if key in inputs:
                    return key
            for key in inputs.keys():
                key_l = str(key).lower()
                if key_l in ("image_output", "filename_prefix"):
                    continue
                if any(token in key_l for token in ("image", "img", "pixels", "source", "reference", "init")):
                    return str(key)
            return "image"

        # 设置图片（图生图必须可写入图片节点）
        image_set_ok = False
        image_node_id = self.image_node_id
        image_param_path = self.image_param_path

        # 若当前配置节点缺失，尝试自动重检
        if not image_node_id or image_node_id not in workflow or not image_param_path:
            detected = self._auto_detect_image_node(workflow)
            if detected:
                image_node_id, image_param_path = detected
                print(f"  [工作流] 自动重检图片节点: {image_node_id}.{image_param_path}")

        if image_node_id and image_param_path and image_node_id in workflow:
            image_set_ok = _set_nested_value(workflow[image_node_id], image_param_path, image_name)
            if image_set_ok:
                self.image_node_id = image_node_id
                self.image_param_path = image_param_path
                print(f"  [工作流] 图片节点 {image_node_id}.{image_param_path} = {image_name}")
            else:
                print(f"  [工作流] 警告: 图片参数路径无效 {image_node_id}.{image_param_path}")

        # 回退策略：如果仍失败，尝试对 upload=image 或类图片输入节点强制写入
        if not image_set_ok:
            for fallback_node_id, node_data in workflow.items():
                if not isinstance(node_data, dict):
                    continue
                class_type = (node_data.get("class_type", "") or "").lower()
                inputs = node_data.get("inputs", {})
                if not isinstance(inputs, dict):
                    continue
                if (
                    inputs.get("upload") == "image"
                    or "loadimage" in class_type
                    or ("image" in class_type and any(token in class_type for token in ("load", "input", "output", "reference", "reader")))
                ):
                    picked_key = _pick_image_key(inputs)
                    inputs[picked_key] = image_name
                    self.image_node_id = str(fallback_node_id)
                    self.image_param_path = f"inputs.{picked_key}"
                    image_set_ok = True
                    print(f"  [工作流] 回退写入图片节点 {fallback_node_id}.inputs.{picked_key} = {image_name}")
                    break

        if not image_set_ok:
            raise ValueError(
                "当前工作流无法写入图片输入节点。请重新上传工作流并确认能自动识别到图片节点（常见如 LoadImage / LoadImageOutput / from outputs 节点）。"
            )

        # 设置提示词（仅当 prompt 不为 None 时才设置）
        if prompt is not None:
            if self.prompt_node_id and self.prompt_param_path:
                if self.prompt_node_id in workflow:
                    prompt_set_ok = _set_nested_value(
                        workflow[self.prompt_node_id], self.prompt_param_path, prompt
                    )
                    if prompt_set_ok:
                        print(f"  [工作流] 提示词节点 {self.prompt_node_id}.{self.prompt_param_path} = {prompt[:100]}...")
                    else:
                        print(f"  [工作流] 警告: 提示词参数路径无效 {self.prompt_node_id}.{self.prompt_param_path}")
                else:
                    print(f"  [工作流] 警告: 提示词节点 {self.prompt_node_id} 不存在于工作流中!")
            else:
                print(f"  [工作流] 警告: 未配置提示词节点!")
        else:
            print(f"  [工作流] 使用工作流中的默认提示词（未传入自定义提示词）")

        # 设置采样参数
        if "31" in workflow:  # KSampler节点
            workflow["31"]["inputs"]["seed"] = seed
            workflow["31"]["inputs"]["steps"] = steps

        if "35" in workflow:  # FluxGuidance节点
            workflow["35"]["inputs"]["guidance"] = guidance

        return {"prompt": workflow}
    
    def _submit_workflow(self, workflow: dict) -> str:
        """提交工作流"""
        url = urljoin(self.server_url, "/api/prompt")
        
        response = self.session.post(
            url,
            json=workflow,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        # 无论成功失败，先尝试解析返回体，便于给出详细错误
        result = None
        raw_text = ""
        try:
            result = response.json()
        except Exception:
            try:
                raw_text = (response.text or "").strip()
            except Exception:
                raw_text = ""

        if response.status_code >= 400:
            detail_parts = []
            if isinstance(result, dict):
                if result.get("error"):
                    detail_parts.append(f"error={result.get('error')}")
                if result.get("detail"):
                    detail_parts.append(f"detail={result.get('detail')}")
                if result.get("node_errors"):
                    detail_parts.append(f"node_errors={result.get('node_errors')}")
            if not detail_parts and raw_text:
                detail_parts.append(raw_text[:1000])
            detail_msg = " | ".join(detail_parts) if detail_parts else "无详细返回体"
            raise Exception(f"ComfyUI 提交失败 HTTP {response.status_code}: {detail_msg}")

        if not isinstance(result, dict):
            raise Exception("ComfyUI 返回格式异常：未返回 JSON")

        if result.get("node_errors"):
            raise Exception(f"工作流节点错误: {result['node_errors']}")

        prompt_id = result.get("prompt_id", "")
        if not prompt_id:
            raise Exception(f"ComfyUI 未返回 prompt_id，响应: {result}")
        return prompt_id
    
    def wait_for_result(self, prompt_id: str, timeout: int = 600) -> dict:
        """
        等待生成完成并返回输出图片信息

        Args:
            prompt_id: 工作流ID
            timeout: 超时时间(秒)，默认600秒(10分钟)

        Returns:
            {"filename": "...", "subfolder": "...", "type": "output|temp"}
        """
        start_time = time.time()
        network_error_count = 0
        max_network_errors = 12
        success_without_images_count = 0
        max_success_without_images = 6
        last_history_payload = None
        
        while time.time() - start_time < timeout:
            time.sleep(5)
            elapsed = int(time.time() - start_time)
            print(f"  已等待 {elapsed}s...")

            try:
                history_item, last_history_payload = self._fetch_history_item(prompt_id, timeout=30)
                network_error_count = 0
            except requests.exceptions.RequestException as e:
                network_error_count += 1
                print(f"  [网络重试 {network_error_count}/{max_network_errors}] /history 请求失败: {e}")
                if network_error_count >= max_network_errors:
                    raise Exception(
                        f"ComfyUI 历史接口连接不稳定（连续失败 {network_error_count} 次）: {e}"
                    )
                continue
            
            if history_item:
                status = history_item.get("status", {})
                if status.get("status_str") == "success":
                    images = self._collect_output_images(history_item)
                    if images:
                        print(f"  [结果] 找到 {len(images)} 张输出图片: {[i.get('filename') for i in images]}")
                        return images[0]
                    success_without_images_count += 1
                    print(
                        f"  [结果重查 {success_without_images_count}/{max_success_without_images}] "
                        f"工作流已成功，但暂未发现可下载图片..."
                    )
                    if success_without_images_count >= max_success_without_images:
                        hint = self._summarize_history_payload(last_history_payload)
                        raise Exception(f"工作流执行成功，但未返回可下载的图片输出。{hint}")
                    continue
                            
                elif status.get("status_str") == "error":
                    raise Exception(f"生成失败: {status}")
                    
        raise TimeoutError(f"等待超时: {timeout}秒")
    
    def _extract_history_item(self, payload: Any, prompt_id: str) -> Optional[Dict[str, Any]]:
        """从不同 ComfyUI history 返回结构中提取指定 prompt_id 的条目。"""
        if isinstance(payload, dict):
            # 结构1: {prompt_id: {...}}
            if prompt_id in payload and isinstance(payload[prompt_id], dict):
                return payload[prompt_id]

            # 结构2: {"prompt_id": "...", "outputs": {...}, ...}
            if str(payload.get("prompt_id", "")) == str(prompt_id) and isinstance(payload.get("outputs"), dict):
                return payload

            # 结构3: 嵌套在 history 字段中
            if "history" in payload:
                return self._extract_history_item(payload.get("history"), prompt_id)

            # 结构4: 仅返回单条 {some_id: {...}}（ID 必须匹配 prompt_id）
            dict_values = [v for v in payload.values() if isinstance(v, dict)]
            if len(payload) == 1 and len(dict_values) == 1:
                lone_key = [k for k in payload.keys()][0]
                lone = dict_values[0]
                if str(lone_key) == str(prompt_id) and any(k in lone for k in ("status", "outputs", "output", "prompt")):
                    return lone

            # 兜底：遍历嵌套值
            for v in payload.values():
                item = self._extract_history_item(v, prompt_id)
                if item:
                    return item
            return None

        if isinstance(payload, list):
            for it in payload:
                item = self._extract_history_item(it, prompt_id)
                if item:
                    return item

        return None

    def _is_history_like_item(self, obj: Any) -> bool:
        return isinstance(obj, dict) and any(k in obj for k in ("status", "outputs", "output", "prompt", "prompt_id"))

    def _score_history_item(self, item: Dict[str, Any], prompt_id: str) -> int:
        """给候选 history 条目打分，prompt_id 不匹配直接淘汰。"""
        if not isinstance(item, dict):
            return -10_000

        # prompt_id 必须严格匹配，防止从 /history 误拿到其他任务的旧结果
        item_pid = str(item.get("prompt_id", "") or "")
        if prompt_id and item_pid != str(prompt_id):
            return -10_000

        score = 0
        status = item.get("status", {})
        if isinstance(status, dict):
            status_str = str(status.get("status_str", "")).lower()
            if status_str == "success":
                score += 40
            elif status_str == "error":
                score -= 20

        if isinstance(item.get("outputs"), dict):
            score += 25
        if "output" in item:
            score += 15

        if item_pid == str(prompt_id):
            score += 60

        try:
            img_count = len(self._collect_output_images(item))
            if img_count > 0:
                score += 100 + min(img_count, 20)
        except Exception:
            pass

        return score

    def _fetch_history_item(self, prompt_id: str, timeout: int = 30) -> Tuple[Optional[Dict[str, Any]], Any]:
        """
        兼容不同 ComfyUI 部署的 history 接口路径和返回结构。
        返回: (history_item, last_payload)
        """
        endpoints = [
            f"/history/{prompt_id}",
            f"/api/history/{prompt_id}",
            "/history",
            "/api/history",
        ]

        last_payload = None
        last_exc = None
        best_item: Optional[Dict[str, Any]] = None
        best_payload = None
        best_score = -10_000

        def _normalize_prompt_candidate(
            candidate: Any, allow_infer_prompt_id: bool = False
        ) -> Optional[Dict[str, Any]]:
            if not isinstance(candidate, dict):
                return None
            if not prompt_id:
                return candidate

            item_pid = str(candidate.get("prompt_id", "") or "")
            if item_pid:
                if item_pid != str(prompt_id):
                    return None
                return candidate

            if not allow_infer_prompt_id:
                return None

            inferred = dict(candidate)
            inferred["prompt_id"] = str(prompt_id)
            return inferred

        for ep in endpoints:
            url = urljoin(self.server_url, ep)
            try:
                response = self.session.get(url, timeout=timeout)
                if response.status_code in (404, 405):
                    continue
                response.raise_for_status()
                payload = response.json()
                last_payload = payload
                candidates: List[Dict[str, Any]] = []
                is_prompt_specific_endpoint = bool(
                    prompt_id and ep.rstrip("/").endswith(f"/{prompt_id}")
                )

                item = self._extract_history_item(payload, prompt_id)
                extracted_allow_infer = bool(
                    is_prompt_specific_endpoint
                    or (
                        prompt_id
                        and isinstance(payload, dict)
                        and prompt_id in payload
                        and isinstance(payload.get(prompt_id), dict)
                    )
                )
                extracted = _normalize_prompt_candidate(
                    item, allow_infer_prompt_id=extracted_allow_infer
                )
                if extracted is not None:
                    candidates.append(extracted)

                if not prompt_id:
                    if self._is_history_like_item(payload):
                        candidates.append(payload)
                    if isinstance(payload, dict):
                        for v in payload.values():
                            if self._is_history_like_item(v):
                                candidates.append(v)
                else:
                    # prompt_id 场景下，避免从 /history 全量接口捞到“其他任务的旧结果”
                    if is_prompt_specific_endpoint and self._is_history_like_item(payload):
                        normalized_payload = _normalize_prompt_candidate(
                            payload, allow_infer_prompt_id=True
                        )
                        if normalized_payload is not None:
                            candidates.append(normalized_payload)

                    # 对全量 history，仅接受带明确 prompt_id 且匹配当前任务的条目
                    if isinstance(payload, dict):
                        values = payload.values()
                    elif isinstance(payload, list):
                        values = payload
                    else:
                        values = []

                    for v in values:
                        if self._is_history_like_item(v):
                            normalized_v = _normalize_prompt_candidate(
                                v, allow_infer_prompt_id=False
                            )
                            if normalized_v is not None:
                                candidates.append(normalized_v)

                for cand in candidates:
                    score = self._score_history_item(cand, prompt_id)
                    if score > best_score:
                        best_score = score
                        best_item = cand
                        best_payload = payload

                # 已命中高质量结果（有图片）就直接返回，减少轮询延迟
                if best_item is not None and best_score >= 140:
                    return best_item, best_payload
            except requests.exceptions.RequestException as e:
                last_exc = e
                continue
            except Exception:
                # JSON 解析或结构异常时，继续尝试下一个端点
                continue

        if last_exc and last_payload is None:
            raise last_exc

        return best_item, (best_payload if best_payload is not None else last_payload)

    def _summarize_history_payload(self, payload: Any) -> str:
        """简要描述 history 返回，便于排查“成功但无图片”问题。"""
        try:
            # 尝试提取候选图片信息
            sample_images = []
            sample_item = self._extract_history_item(payload, "")
            if sample_item:
                sample_images = self._collect_output_images(sample_item)[:6]

            if isinstance(payload, dict):
                keys = list(payload.keys())[:12]
                if sample_images:
                    img_text = ", ".join([f"{x.get('filename')}[{x.get('type')}]" for x in sample_images])
                    return f"history返回键: {keys} | 解析到图片: {img_text}"
                return f"history返回键: {keys}"
            if isinstance(payload, list):
                if sample_images:
                    img_text = ", ".join([f"{x.get('filename')}[{x.get('type')}]" for x in sample_images])
                    return f"history返回列表长度: {len(payload)} | 解析到图片: {img_text}"
                return f"history返回列表长度: {len(payload)}"
            if payload is None:
                return "history接口未返回可解析内容"
            return f"history返回类型: {type(payload).__name__}"
        except Exception:
            return "history返回结构解析失败"

    def _collect_output_images(self, history_item: Dict[str, Any]) -> List[Dict[str, str]]:
        """从 ComfyUI history 条目中提取全部输出图片信息并去重。"""
        outputs = history_item.get("outputs", {}) if isinstance(history_item, dict) else {}
        collected: List[Dict[str, str]] = []
        # key=(filename,subfolder) -> item, 同名时优先 output 类型
        collected_map: Dict[Tuple[str, str], Dict[str, str]] = {}
        order_keys: List[Tuple[str, str]] = []

        image_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
        valid_types = {"output", "temp"}

        def _type_rank(t: str) -> int:
            t = (t or "").lower()
            if t == "output":
                return 2
            if t == "temp":
                return 1
            return 0

        def _push_one(filename: str, subfolder: str = "", file_type: str = "output"):
            if not filename or not isinstance(filename, str):
                return
            # history 里有时会出现路径，统一取文件名
            if "\\" in filename or "/" in filename:
                filename = Path(filename).name
            suffix = Path(filename).suffix.lower()
            if suffix and suffix not in image_exts:
                return

            normalized_type = str(file_type or "output").lower()
            if normalized_type not in valid_types:
                normalized_type = "output"

            key = (filename, subfolder or "")
            item = {
                "filename": filename,
                "subfolder": subfolder or "",
                "type": normalized_type,
            }

            old = collected_map.get(key)
            if old is None:
                collected_map[key] = item
                order_keys.append(key)
                return

            # 同 key 出现多次时，优先保留 output
            if _type_rank(item["type"]) > _type_rank(old.get("type", "")):
                collected_map[key] = item

        def _extract_images(obj: Any, depth: int = 0):
            if depth > 8:
                return
            if isinstance(obj, dict):
                # 标准结构: {"filename":"x.png","subfolder":"","type":"output"}
                filename = obj.get("filename")
                if isinstance(filename, str):
                    _push_one(
                        filename=filename,
                        subfolder=str(obj.get("subfolder", "") or ""),
                        file_type=str(obj.get("type", "output") or "output"),
                    )

                # 常见容器键
                for key in ("images", "image", "results", "result", "outputs", "output"):
                    if key in obj:
                        _extract_images(obj.get(key), depth + 1)

                # 泛化遍历，兼容自定义节点结构
                for value in obj.values():
                    _extract_images(value, depth + 1)
                return

            if isinstance(obj, (list, tuple)):
                for item in obj:
                    _extract_images(item, depth + 1)
                return

            # 极端兼容: 某些自定义节点可能直接返回文件名字符串
            if isinstance(obj, str):
                if obj.startswith("http://") or obj.startswith("https://"):
                    return
                suffix = Path(obj).suffix.lower()
                if suffix in image_exts:
                    _push_one(Path(obj).name, "", "output")

        # 先尝试“指定输出节点”，若拿到 output 类型结果就优先返回
        output_node_only_map: Dict[Tuple[str, str], Dict[str, str]] = {}
        output_node_order: List[Tuple[str, str]] = []

        def _collect_from_output_node(node_obj: Any):
            # 复用提取逻辑，先写到主 map，再拷出增量
            before_keys = set(collected_map.keys())
            _extract_images(node_obj)
            after_keys = [k for k in order_keys if k not in before_keys]
            for k in after_keys:
                output_node_order.append(k)
                output_node_only_map[k] = collected_map[k]

        if self.output_node_id in outputs:
            _collect_from_output_node(outputs[self.output_node_id])
            node_items = [output_node_only_map[k] for k in output_node_order if k in output_node_only_map]
            node_output_items = [it for it in node_items if it.get("type") == "output"]
            if node_output_items:
                return node_output_items
            # 输出节点存在但没有 output 类型，返回所有该节点的图片
            if node_items:
                return node_items

        # 输出节点不在 outputs 中，直接报错，不兜底
        available_nodes = list(outputs.keys()) if isinstance(outputs, dict) else []
        raise Exception(
            f"输出节点 '{self.output_node_id}' 未在 ComfyUI 返回的 outputs 中找到。"
            f"\n可用的输出节点: {available_nodes}"
            f"\n请检查工作流配置中的输出节点ID是否正确。"
        )

    def wait_for_all_results(self, prompt_id: str, timeout: int = 600) -> List[Dict[str, str]]:
        """
        等待工作流完成并返回全部输出图片信息。

        Returns:
            [{"filename": "...", "subfolder": "...", "type": "temp|output"}, ...]
        """
        start_time = time.time()
        network_error_count = 0
        max_network_errors = 12
        success_without_images_count = 0
        max_success_without_images = 6
        last_history_payload = None

        while time.time() - start_time < timeout:
            time.sleep(5)
            elapsed = int(time.time() - start_time)
            print(f"  工茬瓑寰?{elapsed}s...")

            try:
                history_item, last_history_payload = self._fetch_history_item(prompt_id, timeout=30)
                network_error_count = 0
            except requests.exceptions.RequestException as e:
                network_error_count += 1
                print(f"  [网络重试 {network_error_count}/{max_network_errors}] /history 请求失败: {e}")
                if network_error_count >= max_network_errors:
                    raise Exception(
                        f"ComfyUI 历史接口连接不稳定（连续失败 {network_error_count} 次）: {e}"
                    )
                continue

            if history_item:
                status = history_item.get("status", {})
                if status.get("status_str") == "success":
                    images = self._collect_output_images(history_item)
                    if images:
                        return images
                    success_without_images_count += 1
                    print(
                        f"  [结果重查 {success_without_images_count}/{max_success_without_images}] "
                        f"工作流已成功，但暂未发现可下载图片..."
                    )
                    if success_without_images_count >= max_success_without_images:
                        hint = self._summarize_history_payload(last_history_payload)
                        raise Exception(f"工作流执行成功，但未返回可下载的图片输出。{hint}")
                    continue
                if status.get("status_str") == "error":
                    raise Exception(f"生成成失败败: {status}")

        raise TimeoutError(f"等待超时: {timeout}秒")

    def image_to_image_all(self, source_image: str, prompt: str = None,
                           seed: int = None, steps: int = 20,
                           guidance: float = 2.5, output_dir: str = "./output/generated") -> List[str]:
        """
        图生图并下载全部输出图片到本地。

        Returns:
            本地结果路径列表
        """
        if not self.server_url:
            raise ValueError("服厤缃瓹omfyUI服制务器ㄥ地址")

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        print(f"[1/5] 中婁传图剧墖...")
        image_name = self.upload_image(source_image)
        print(f"  中婁传成功功: {image_name}")

        print(f"[2/5] 鏋勫缓工ヤ作流?.")
        workflow = self._build_workflow(
            image_name=image_name,
            prompt=prompt or "",
            seed=seed if seed is not None else random.randint(0, 999999999999999),
            steps=steps,
            guidance=guidance
        )

        print(f"[3/5] 提愪氦工ヤ作流?.")
        prompt_id = self._submit_workflow(workflow)
        print(f"  提愪氦成功功, prompt_id: {prompt_id}")

        print(f"[4/5] 绛夊緟生成成完步成...")
        output_images = self.wait_for_all_results(prompt_id)
        print(f"  生成成成功功! 入?{len(output_images)} 开?")

        print(f"[5/5] 中嬭浇生成成的勫浘鐗?.")
        local_paths: List[str] = []
        base_name = Path(source_image).stem
        ts = int(time.time())

        for idx, item in enumerate(output_images, start=1):
            filename = item["filename"]
            subfolder = item.get("subfolder", "")
            file_type = item.get("type", "temp")
            suffix = Path(filename).suffix or ".png"
            output_path = Path(output_dir) / f"generated_{base_name}_{ts}_{idx}{suffix}"
            self.download_result(
                filename=filename,
                output_path=str(output_path),
                subfolder=subfolder,
                file_type=file_type
            )
            local_paths.append(str(output_path))
            print(f"  中嬭浇[{idx}/{len(output_images)}]: {output_path}")

        return local_paths
    def download_result(self, filename: str, output_path: str,
                        subfolder: str = "", file_type: str = "temp") -> str:
        """
        下载生成的图片到本地
        
        Args:
            filename: 服务器上的文件名
            output_path: 本地保存路径
            subfolder: 子文件夹
            file_type: 文件类型 (temp/output)
            
        Returns:
            本地保存路径
        """
        # 先按给定类型下载，失败时自动在 temp/output 间切换再试一次
        types_to_try = [file_type]
        alt_type = "output" if file_type == "temp" else "temp"
        if alt_type not in types_to_try:
            types_to_try.append(alt_type)

        last_err = None
        for one_type in types_to_try:
            url = urljoin(
                self.server_url,
                f"/view?filename={filename}&subfolder={subfolder}&type={one_type}"
            )
            try:
                response = self.session.get(url, timeout=60)
                response.raise_for_status()
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                return output_path
            except Exception as e:
                last_err = e
                continue

        raise Exception(f"下载结果失败: {filename} ({last_err})")
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        url = urljoin(self.server_url, "/prompt")
        response = self.session.get(url, timeout=10)
        response.raise_for_status()
        return response.json()

