import pytest
from carnivore import Carnivore

MIN_SIZE_WITH_IMAGES = 1000  # Adjust this value as needed


@pytest.fixture(scope="module")
def carnivore():
    carnivore = Carnivore()

    async def async_print(message: str):
        print(message)

    carnivore.set_progress_callback(async_print)
    return carnivore


async def _test_common(carnivore, url, markdown_min_size):
    output = await carnivore.archive(url)
    assert output["metadata"]["title"], "Title not found in output"
    assert output["content"]["html"], "HTML content not found in output"
    assert output["content"]["markdown"], "Markdown content not found in output"
    assert (
        len(output["content"]["markdown"]) >= markdown_min_size
    ), "Markdown content is too small"


@pytest.mark.asyncio
async def test_dynamic_content_loading(carnivore):
    await _test_common(
        carnivore,
        "https://battleda.sh/blog/ea-account-takeover",
        MIN_SIZE_WITH_IMAGES,
    )


@pytest.mark.asyncio
async def test_visibility_hidden(carnivore):
    await _test_common(
        carnivore,
        "https://mp.weixin.qq.com/s/koaLJvsFLkfi_j3HKIi6Dw",
        MIN_SIZE_WITH_IMAGES,
    )


@pytest.mark.skip(
    reason="This test costs too much time because a lot of large images to download"
)
@pytest.mark.asyncio
async def test_no_timeout(carnivore):
    await _test_common(
        carnivore,
        "https://jhftss.github.io/A-New-Era-of-macOS-Sandbox-Escapes/",
        MIN_SIZE_WITH_IMAGES,
    )


if __name__ == "__main__":
    pytest.main()
