import requests
import os
import time
import zipfile
import io

# --- 配置信息 ---
# 请替换为您的 API Token
TOKEN = "eyJ0eXBlIjoiSldUIiwiYWxnIjoiSFM1MTIifQ.eyJqdGkiOiI1MzAwMDg0MyIsInJvbCI6IlJPTEVfUkVHSVNURVIiLCJpc3MiOiJPcGVuWExhYiIsImlhdCI6MTc2NDk1MzgzNCwiY2xpZW50SWQiOiJsa3pkeDU3bnZ5MjJqa3BxOXgydyIsInBob25lIjoiMTg5MjQ5Mzk4MDIiLCJvcGVuSWQiOm51bGwsInV1aWQiOiI5ZGYzMGNjMC01MTNiLTQyMDAtYWFjNy1kNDM0YjE4OWZmMzIiLCJlbWFpbCI6IiIsImV4cCI6MTc2NjE2MzQzNH0.Im3STnoIJX5dY9lXVHuk0wskKDTHu5KN7jnaqRqCcUvUqANTELTEZKtMZhPt2cuFNo5OGwof3kt6WTXccIFmlw"
# 请替换为您的本地 PDF 文件路径
FILE_PATH = "paper.pdf"  # 例如 "C:/Users/Admin/Documents/demo.pdf"

# --- API 端点 ---
GET_UPLOAD_URL_API = "https://mineru.net/api/v4/file-urls/batch"
GET_RESULT_API_TEMPLATE = "https://mineru.net/api/v4/extract-results/batch/{}"

# --- 脚本主逻辑 ---
def main():
    """
    主函数，执行文件上传、状态查询、结果下载和解析的全过程。
    """
    if not os.path.exists(FILE_PATH):
        print(f"错误：文件 '{FILE_PATH}' 不存在。")
        return

    file_name = os.path.basename(FILE_PATH)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}"
    }

    # 1. 获取文件上传链接
    print("步骤 1/4: 正在申请文件上传链接...")
    upload_data = {
        "files": [{"name": file_name}],
        "model_version": "vlm" # 或者使用 "pipeline"
    }
    try:
        response = requests.post(GET_UPLOAD_URL_API, headers=headers, json=upload_data)
        response.raise_for_status()
        result = response.json()

        if result.get("code") != 0:
            print(f"申请上传链接失败: {result.get('msg')}")
            return

        batch_id = result["data"]["batch_id"]
        upload_url = result["data"]["file_urls"][0]
        print(f"成功获取上传链接。Batch ID: {batch_id}")

    except requests.exceptions.RequestException as e:
        print(f"请求上传链接时发生网络错误: {e}")
        return

    # 2. 上传文件
    print("步骤 2/4: 正在上传文件...")
    try:
        with open(FILE_PATH, 'rb') as f:
            # 上传文件时不需要设置 Content-Type
            upload_response = requests.put(upload_url, data=f, headers={"Authorization": None})
            upload_response.raise_for_status()
        print("文件上传成功。")
    except requests.exceptions.RequestException as e:
        print(f"文件上传失败: {e}")
        return
    except IOError as e:
        print(f"读取文件失败: {e}")
        return


    # 3. 轮询解析结果
    print("步骤 3/4: 等待云端解析完成...")
    result_url = GET_RESULT_API_TEMPLATE.format(batch_id)
    while True:
        try:
            result_response = requests.get(result_url, headers=headers)
            result_response.raise_for_status()
            task_info = result_response.json()

            if task_info.get("code") != 0:
                print(f"查询任务状态失败: {task_info.get('msg')}")
                break

            task_status = task_info["data"]["extract_result"][0]["state"]
            if task_status == "done":
                print("文件解析成功！")
                full_zip_url = task_info["data"]["extract_result"][0]["full_zip_url"]
                break
            elif task_status == "failed":
                err_msg = task_info["data"]["extract_result"][0].get("err_msg", "未知错误")
                print(f"文件解析失败: {err_msg}")
                return
            else:
                print(f"当前任务状态: {task_status}，将在 1 秒后重试...")
                time.sleep(1)

        except requests.exceptions.RequestException as e:
            print(f"查询结果时发生网络错误: {e}")
            time.sleep(1)

    # 4. 下载并提取 Markdown 内容
    print("步骤 4/4: 正在下载并提取 Markdown 内容...")
    try:
        zip_response = requests.get(full_zip_url)
        zip_response.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(zip_response.content)) as z:
            markdown_file_name_in_zip = None
            for name in z.namelist():
                if name.endswith('.md'):
                    markdown_file_name_in_zip = name
                    break
            
            if markdown_file_name_in_zip:
                # 从压缩包中读取 Markdown 内容
                with z.open(markdown_file_name_in_zip) as md_file:
                    markdown_content = md_file.read().decode('utf-8')
                
                # 创建新的本地文件名 (例如: demo.pdf -> demo.md)
                base_name = os.path.splitext(file_name)[0]
                output_filename = f"{base_name}.md"
                
                # 将内容写入新文件
                with open(output_filename, 'w', encoding='utf-8') as f_out:
                    f_out.write(markdown_content)
                
                print("\n--- 操作成功 ---")
                print(f"Markdown 内容已成功保存到文件: {os.path.abspath(output_filename)}")

            else:
                print("错误：在结果压缩包中未找到 Markdown 文件。")

    except requests.exceptions.RequestException as e:
        print(f"下载结果文件失败: {e}")
    except zipfile.BadZipFile:
        print("下载的文件不是一个有效的 ZIP 压缩包。")
    except IOError as e:
        print(f"写入文件时发生错误: {e}")


if __name__ == "__main__":
    main()