"""Windows 系统 OCR 引擎（T-21）。

实现 ocr/base.py 冻结契约，经 Windows.Media.Ocr（WinRT）识别，离线、图片不出本机。

实现方式：调用系统自带 PowerShell 执行本模块内嵌脚本。理由：
- .NET Framework 对 WindowsRuntime 类型的元数据投影停留在 UniversalApiContract v7
  （OcrLine/Blocks 坐标属性为 v13 扩展，桌面投影不可见），而 PowerShell/Python 均
  不新增第三方依赖即可用 v7 的 OcrWord.BoundingRect 聚合出行级坐标；
- 纯标准库（subprocess/tempfile/json），零新增依赖（R-09/R-10 约束）；
- 未装 OCR 语言包时探测返回可读引导而非崩溃。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass

from PySide6.QtGui import QImage

from .base import OcrError, OcrResult, TextBlock

# 语言包探测脚本（无泛型/无 backtick，可安全经 -Command 传递；输出 JSON）
_PROBE_PS = ("$ErrorActionPreference='Stop';"
             "[Windows.Media.Ocr.OcrEngine,Windows.Foundation.UniversalApiContract,"
             "ContentType=WindowsRuntime] | Out-Null;"
             "$l=[Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages;"
             "$o=@(); foreach($x in $l){$o+=$x.LanguageTag};"
             "ConvertTo-Json -Compress -InputObject @{count=$l.Count;langs=$o}")

# 识别主脚本（含 AsTask 泛型反射，必须以文件方式执行，避免引号转义问题）
_OCR_PS = r'''
param([Parameter(Mandatory=$true)][string]$ImagePath, [string]$LanguageTag = '')
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$ag = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
                   $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($t2, $rt) { $m = $ag.MakeGenericMethod($rt); $n = $m.Invoke($null, @($t2)); $null = $n.Wait(-1); $n.Result }
[Windows.Media.Ocr.OcrEngine, Windows.Foundation.UniversalApiContract, ContentType=WindowsRuntime] | Out-Null
[Windows.Globalization.Language, Windows.Foundation.FoundationContract, ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.StorageFile, Windows.Foundation.UniversalApiContract, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation.UniversalApiContract, ContentType=WindowsRuntime] | Out-Null
$avail = [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages
if ($avail.Count -eq 0) { Write-Output 'NO-LANGUAGE'; exit 2 }
$engine = null
if ($LanguageTag -ne '') {
    try { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage((New-Object Windows.Globalization.Language($LanguageTag))) }
    catch { $engine = $null }
}
if ($null -eq $engine) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
if ($null -eq $engine) {
    foreach ($x in $avail) {
        try { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($x); if ($engine) { break } } catch {}
    }
}
if ($null -eq $engine) { Write-Output 'NO-ENGINE'; exit 2 }
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
try {
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bmp = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $res = Await ($engine.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
    $lines = @()
    foreach ($ln in $res.Lines) {
        $minX = $null; $minY = $null; $maxR = $null; $maxB = $null
        foreach ($wd in $ln.Words) {
            $b = $wd.BoundingRect
            $x = [int]$b.X; $y = [int]$b.Y; $w2 = [int]$b.Width; $h2 = [int]$b.Height
            if ($null -eq $minX -or $x -lt $minX) { $minX = $x }
            if ($null -eq $minY -or $y -lt $minY) { $minY = $y }
            if ($null -eq $maxR -or ($x + $w2) -gt $maxR) { $maxR = $x + $w2 }
            if ($null -eq $maxB -or ($y + $h2) -gt $maxB) { $maxB = $y + $h2 }
        }
        $lines += [pscustomobject]@{
            text = $ln.Text
            x = $(if ($null -eq $minX) { 0 } else { $minX })
            y = $(if ($null -eq $minY) { 0 } else { $minY })
            width = $(if ($null -eq $maxR) { 0 } else { $maxR - $minX })
            height = $(if ($null -eq $maxB) { 0 } else { $maxB - $minY })
        }
    }
    [pscustomobject]@{ engine = $engine.RecognizerLanguage.LanguageTag; text = $res.Text; lines = $lines } |
        ConvertTo-Json -Depth 3 -Compress
} finally { $stream.Dispose() }
'''

_INSTALL_GUIDANCE = (
    "需要安装系统 OCR 语言包：设置 → 时间和语言 → 语言和区域 → 添加语言，"
    "勾选「光学字符识别」选项；安装后重试"
)


@dataclass
class _Probe:
    supported: bool = False
    langs: tuple[str, ...] = ()
    error: str = ""


class WindowsOcrEngine:
    """Windows 系统 OCR（Windows.Media.Ocr）引擎实现。"""

    name = "windows"

    def __init__(self) -> None:
        self._probe: _Probe | None = None

    # ---------- 契约 ----------

    def available(self) -> bool:
        return self._detect().supported

    def unavailable_reason(self) -> str:
        p = self._detect()
        if p.supported:
            return ""
        return p.error

    def recognize(self, image: QImage) -> OcrResult:
        if image is None or image.isNull() or image.width() <= 0 or image.height() <= 0:
            raise OcrError("图像为空，无法识别")
        if not self.available():
            raise OcrError(self.unavailable_reason() or "Windows OCR 引擎不可用")
        data = self._run(image)
        lines = data.get("lines") or []
        blocks = tuple(
            TextBlock(text=str(ln.get("text", "")),
                      x=int(ln.get("x", 0)), y=int(ln.get("y", 0)),
                      width=int(ln.get("width", 0)), height=int(ln.get("height", 0)))
            for ln in lines
        )
        text = str(data.get("text", ""))
        return OcrResult(text=text.strip(), blocks=blocks, engine=self.name)

    # ---------- 内部实现 ----------

    def _detect(self) -> _Probe:
        if self._probe is not None:
            return self._probe
        probe = _Probe()
        if sys.platform != "win32":
            probe.error = "Windows OCR 仅支持 Windows 10 及以上系统"
            self._probe = probe
            return probe
        try:
            out = self._ps(_PROBE_PS)
            info = json.loads(out)
            langs = tuple(info.get("langs") or [])
            if info.get("count", 0) > 0 and langs:
                probe.supported = True
                probe.langs = langs
            else:
                probe.error = _INSTALL_GUIDANCE
        except (OcrError, ValueError):
            probe.error = _INSTALL_GUIDANCE if sys.platform == "win32" else "系统 OCR 组件不可用"
        self._probe = probe
        return probe

    def _run(self, image: QImage) -> dict:
        tmpdir = tempfile.mkdtemp(prefix="snippin_ocr_")
        png = os.path.join(tmpdir, "capture.png")
        script = os.path.join(tmpdir, f"ocr_{uuid.uuid4().hex}.ps1")
        try:
            if not image.save(png, "PNG"):
                raise OcrError("选区图像保存失败，无法识别")
            with open(script, "w", encoding="utf-8") as f:
                f.write(_OCR_PS)
            out = self._ps("-File", script, "-ImagePath", png)
            if out.strip() in ("NO-LANGUAGE", "NO-ENGINE"):
                raise OcrError(_INSTALL_GUIDANCE)
            try:
                return json.loads(out)
            except json.JSONDecodeError as exc:
                raise OcrError("OCR 结果解析失败，请重试或反馈日志") from exc
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @staticmethod
    def _ps(*args: str) -> str:
        flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
        try:
            proc = subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", *args],
                capture_output=True, text=True, encoding="utf-8",
                timeout=30, check=False, creationflags=flags)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise OcrError("无法调用系统 PowerShell（Windows 10/11 内置组件）") from exc
        if proc.returncode != 0 and not proc.stdout.strip():
            raise OcrError("OCR 组件调用失败，请确认系统语言版本为 Windows 10 及以上")
        return proc.stdout
