import pytest
import carnivore
from carnivore.cache import _generate_key

MARKDOWN_MIN_SIZE_WITH_IMAGES = 1000  # Adjust this value as needed


@pytest.fixture(scope="module")
def carnivore_instance():
    instance = carnivore.Carnivore(carnivore.SUPPORTED_FORMATS, "data")

    async def async_print(message: str):
        print(message)

    instance.set_progress_callback(async_print)
    return instance


def file_size_check(file_path, min_size):
    with open(file_path, "rb") as f:
        size = len(f.read())
        assert (
            size >= min_size
        ), f"Content of {file_path} is too small. Size: {size}, expected: >={min_size}"


async def _test_common(
    carnivore_instance, url, markdown_min_size=None, pdf_min_size=None
):
    output = await carnivore_instance.archive(url)
    assert output["metadata"]["title"], "Title not found in output"
    for format in carnivore.SUPPORTED_FORMATS:
        assert output["files"][format], f"{format} content not found in output"
    if markdown_min_size:
        file_size_check(output["files"]["markdown"], markdown_min_size)
    if pdf_min_size:
        file_size_check(output["files"]["pdf"], pdf_min_size)
    return output


def test_cache_key_includes_runtime_configuration():
    default_instance = carnivore.Carnivore(carnivore.SUPPORTED_FORMATS, "data")
    zenrows_instance = carnivore.Carnivore(
        carnivore.SUPPORTED_FORMATS,
        "data",
        zenrows_api_key="secret-api-key",
        zenrows_premium_proxies=True,
    )
    oxylabs_instance = carnivore.Carnivore(
        carnivore.SUPPORTED_FORMATS,
        "data",
        oxylabs_user="user:secret-password",
        oxylabs_js_rendering=True,
    )

    args = ("https://example.com",)
    default_key = _generate_key(
        "_get_rendered_html_from_url",
        args,
        {},
        default_instance.get_cache_namespace(),
    )
    zenrows_key = _generate_key(
        "_get_rendered_html_from_url",
        args,
        {},
        zenrows_instance.get_cache_namespace(),
    )
    oxylabs_key = _generate_key(
        "_get_rendered_html_from_url",
        args,
        {},
        oxylabs_instance.get_cache_namespace(),
    )

    assert len({default_key, zenrows_key, oxylabs_key}) == 3
    assert "secret-api-key" not in str(zenrows_instance.get_cache_namespace())
    assert "secret-password" not in str(oxylabs_instance.get_cache_namespace())


@pytest.mark.asyncio
async def test_dynamic_content_loading(carnivore_instance):
    await _test_common(
        carnivore_instance,
        "https://battleda.sh/blog/ea-account-takeover",
        markdown_min_size=MARKDOWN_MIN_SIZE_WITH_IMAGES,
    )


@pytest.mark.asyncio
async def test_visibility_hidden(carnivore_instance):
    await _test_common(
        carnivore_instance,
        "https://mp.weixin.qq.com/s/koaLJvsFLkfi_j3HKIi6Dw",
        markdown_min_size=MARKDOWN_MIN_SIZE_WITH_IMAGES,
    )


@pytest.mark.asyncio
async def test_no_timeout(carnivore_instance):
    await _test_common(
        carnivore_instance,
        "https://jhftss.github.io/A-New-Era-of-macOS-Sandbox-Escapes/",
        markdown_min_size=MARKDOWN_MIN_SIZE_WITH_IMAGES,
    )


@pytest.mark.asyncio
async def test_pdf_images_no_lazy_loading(carnivore_instance):
    await _test_common(
        carnivore_instance,
        "https://www.rfleury.com/p/demystifying-debuggers-part-2-the",
        markdown_min_size=MARKDOWN_MIN_SIZE_WITH_IMAGES,
        pdf_min_size=5 * 1024 * 1024,
    )


@pytest.mark.asyncio
async def test_http_headers(carnivore_instance):
    output = await _test_common(
        carnivore_instance,
        "http://gethttp.info/",
    )
    with open(output["files"]["full_html"], "r") as f:
        html = f.read()
    assert "Headless" not in html


if __name__ == "__main__":
    pytest.main()
