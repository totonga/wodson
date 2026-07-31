from pathlib import Path

from wodson.atfx import AtfxFile
from wodson.utils import FilePathResolver

DATA_DIR = Path(__file__).resolve().parent / "data" / "openatfx"

AOFILE_ATFX = DATA_DIR / "external_with_flags_aofile.atfx"
EC_ATFX_FILE = DATA_DIR / "example_asam36.atfx"


def test_aofile_ao_location():
    with AtfxFile(AOFILE_ATFX) as atfx:
        df = atfx.con_i.query({"ExtCompFile": {}, "$attributes": {"name": 1, "ao_location": 1}})
        a = atfx.con_i.mc.attribute("ExtCompFile", "ao_location")

        locations = df.ao_location.to_list()
        assert len(locations) > 0
        assert all(loc is not None and loc != "" for loc in locations)

        pr = FilePathResolver(atfx.con_i.context)
        resolved_a = pr.resolve_urls(input_urls=locations, attr_or_mode=a)
        assert all(Path(p).is_absolute() for p in resolved_a)
        assert all(Path(p).exists() for p in resolved_a)

        assert FilePathResolver._get_attribute_path_mode(a) == FilePathResolver.AttrMode.MANAGED
        resolved_m = pr.resolve_urls(input_urls=locations, attr_or_mode=FilePathResolver.AttrMode.MANAGED)
        assert all(Path(p).is_absolute() for p in resolved_m)
        assert all(Path(p).exists() for p in resolved_m)

        assert resolved_a == resolved_m


def test_ec_filename_url():
    with AtfxFile(EC_ATFX_FILE) as atfx:
        df = atfx.con_i.query({"ec": {}, "$attributes": {"name": 1, "filename_url": 1}})
        a = atfx.con_i.mc.attribute("ec", "filename_url")

        locations = df.filename_url.to_list()
        assert len(locations) > 0
        assert all(loc is not None and loc != "" for loc in locations)

        pr = FilePathResolver(atfx.con_i.context)
        resolved_a = pr.resolve_urls(input_urls=locations, attr_or_mode=a)
        assert all(Path(p).is_absolute() for p in resolved_a)
        assert all(Path(p).exists() for p in resolved_a)

        assert FilePathResolver._get_attribute_path_mode(a) == FilePathResolver.AttrMode.ROOT
        resolved_m = pr.resolve_urls(input_urls=locations, attr_or_mode=FilePathResolver.AttrMode.ROOT)
        assert all(Path(p).is_absolute() for p in resolved_m)
        assert all(Path(p).exists() for p in resolved_m)

        assert resolved_a == resolved_m
