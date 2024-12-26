import pytest
import carnivore

MIN_SIZE_WITH_IMAGES = 1000  # Adjust this value as needed


@pytest.fixture(scope="module")
def carnivore_instance():
    instance = carnivore.Carnivore(carnivore.SUPPORTED_FORMATS, "data")

    async def async_print(message: str):
        print(message)

    instance.set_progress_callback(async_print)
    return instance


async def _test_common(carnivore_instance, url, markdown_min_size):
    output = await carnivore_instance.archive(url)
    assert output["metadata"]["title"], "Title not found in output"
    assert output["files"]["html"], "HTML content not found in output"
    assert output["files"]["markdown"], "Markdown content not found in output"
    with open(output["files"]["markdown"], "r") as f:
        size = len(f.read())
        assert size >= markdown_min_size, "Markdown content is too small"


@pytest.mark.asyncio
async def test_dynamic_content_loading(carnivore_instance):
    await _test_common(
        carnivore_instance,
        "https://battleda.sh/blog/ea-account-takeover",
        MIN_SIZE_WITH_IMAGES,
    )


@pytest.mark.asyncio
async def test_visibility_hidden(carnivore_instance):
    await _test_common(
        carnivore_instance,
        "https://mp.weixin.qq.com/s/koaLJvsFLkfi_j3HKIi6Dw",
        MIN_SIZE_WITH_IMAGES,
    )


@pytest.mark.skip(
    reason="This test costs too much time because a lot of large images to download"
)
@pytest.mark.asyncio
async def test_no_timeout(carnivore_instance):
    await _test_common(
        carnivore_instance,
        "https://jhftss.github.io/A-New-Era-of-macOS-Sandbox-Escapes/",
        MIN_SIZE_WITH_IMAGES,
    )


if __name__ == "__main__":
    pytest.main()
