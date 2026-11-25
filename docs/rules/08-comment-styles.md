# 08 — Comments and Documentation Style

## ⚠️ Mandatory Gate

All **public classes**, **public methods**, and **public functions** in this project must have Chinese docstrings. Code submitted without compliant docstrings on public interfaces will be **rejected at review**. No exceptions.

"Public" means anything not prefixed with `_`. This includes all methods on `ChainBase` subclasses, `_ModuleBase` subclasses, Pydantic schema classes, and endpoint functions.

---

## Docstring Format

Short, label-style docstrings should follow the surrounding code style and must not gain a period mechanically. Complete sentences that explain non-obvious behavior should use normal Chinese punctuation.

### Single-line (for simple, obvious descriptions)

```python
def get_name() -> str:
    """获取模块名称"""
    return "Qbittorrent"
```

### Multi-line (for methods with parameters, return values, or non-obvious behavior)

```python
def manual_transfer(
    self,
    fileitems: List[FileItem],
    target_path: Path,
) -> Optional[TransferInfo]:
    """
    按用户选择的源文件和目标目录执行手动整理

    :param fileitems: 待整理的源文件清单
    :param target_path: 媒体库目标目录
    :return: 成功时返回整理结果，失败时返回 None
    """
    ...
```

### Class docstrings

```python
class TransferChain(ChainBase):
    """
    文件整理链，负责识别源文件、执行入库整理并同步整理结果
    """
```

---

## Docstring Language Rule

- **Default:** Chinese.
- **Exception:** If the surrounding file is entirely and consistently in English, match the local style.
- Do not mix languages within a single docstring. Pick one and stay consistent for the whole file.

---

## Inline Comments

**Only add an inline or block comment when the WHY is non-obvious.** Good reasons to add a comment:

- A hidden external constraint (e.g., "this API returns stale data for up to 60 seconds after update")
- A subtle invariant the code must maintain
- A workaround for a specific third-party bug
- Call ordering or initialization requirements that are not apparent from the code
- Compatibility reasons with a specific client version or protocol

**Do not add a comment when:**

- The code already explains itself through well-named identifiers
- The comment would just restate what the code does in words
- The logic is straightforward branching or assignment

---

## Correct Examples

```python
# qBittorrent API 在添加种子后立即查询时可能返回空，需要短暂等待
time.sleep(0.5)
result = self.client.get_torrent(hash_id)
```

```python
# 此处必须先检查 module 是否已初始化，否则多线程并发调用时 get_instances() 可能返回空列表
if not self._initialized:
    self.init_module()
```

---

## Incorrect Examples

```python
# 获取整理历史  ← 这只是在重述代码，不需要
histories = TransferHistoryOper().list()

# 如果 result 为 None 则返回  ← 无意义
if result is None:
    return None

# change starts here  ← 噪音，禁止
# fix: handle edge case  ← 噪音，改成提交信息里写
```

---

## Comment Placement

- Place block comments **above** the code they describe, not on the same line.
- Use same-line end-of-line comments only for very short clarifications (e.g., unit of a constant).
- For long explanations, prefer a block comment above the code rather than a multiline end-of-line comment.

```python
# 优先使用已有的下载目录映射，避免重复计算路径
effective_dir = self._resolve_download_dir(torrent) or download_dir
```

---

## Stale Comment Rule

When modifying code, update or remove any comment that no longer accurately describes the implementation. A stale comment is worse than no comment — it actively misleads future readers.

---

## Prohibited Patterns

| Pattern | Why |
|---|---|
| `# change starts here` / `# change ends here` | Editorial noise; belongs in git history, not source |
| `# TODO` without context or assignee | Accepted only when the deferral is genuinely unavoidable and the reason is documented |
| `# FIXME` left in submitted code | Fix it now or document exactly why it cannot be fixed |
| `# this is important` | Every line of code is important; this adds nothing |
| Commented-out dead code | Delete it; git history preserves it |
| Docstrings in English on new public interfaces | Violation of the mandatory Chinese docstring gate |

*Last Updated: 2026-05-25*
