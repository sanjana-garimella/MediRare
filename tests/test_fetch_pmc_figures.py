from __future__ import annotations

from unittest.mock import patch

from cv.fetch_pmc_figures import classify_figure, fetch_pmc_figures, pmc_s3_prefix


def test_classify_figure_imaging_ct():
    assert classify_figure("CT scan showing bilateral pleural effusion") == "imaging"


def test_classify_figure_imaging_echocardiogram_stem_regression():
    # Regression: a trailing \b directly after "echocardiogra" never matches,
    # since real words continue "...phy"/"...m" — must use \w* instead.
    assert classify_figure("Echocardiogram demonstrating pericardial effusion") == "imaging"


def test_classify_figure_histology_stain():
    assert classify_figure("H&E stain showing glomerular necrosis") == "histology"


def test_classify_figure_histology_before_rash_order_regression():
    # Regression: histology must be checked before rash_image so "necrotic"
    # in a histology caption doesn't get wrongly tagged as a skin photo.
    assert classify_figure("Skin biopsy revealing amorphous necrotic debris") == "histology"


def test_classify_figure_rash_image():
    assert classify_figure("Malar rash across the cheeks") == "rash_image"


def test_classify_figure_lab_chart():
    assert classify_figure("Trend of anti-dsDNA titer over 6 months") == "lab_chart"


def test_classify_figure_other_no_keyword_match():
    assert classify_figure("Small subcentimeter prevascular lymph nodes") == "other"


_S3_MULTI_VERSION_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Name>pmc-oa-opendata</Name>
  <Prefix>PMC13242597.</Prefix>
  <CommonPrefixes><Prefix>PMC13242597.2/</Prefix></CommonPrefixes>
  <CommonPrefixes><Prefix>PMC13242597.10/</Prefix></CommonPrefixes>
</ListBucketResult>"""

_ARTICLE_XML = b"""<?xml version="1.0"?>
<pmc-articleset>
<article xmlns:xlink="http://www.w3.org/1999/xlink">
<fig>
<label>Figure 1</label>
<caption><p>CT scan showing bilateral pleural effusion.</p></caption>
<graphic xlink:href="fig1.jpg"/>
</fig>
</article>
</pmc-articleset>"""


def test_pmc_s3_prefix_picks_numeric_max_not_lexicographic():
    # Regression: a plain string sort ranks ".10/" below ".2/" — must sort
    # by the numeric version instead.
    with patch("cv.fetch_pmc_figures._get", return_value=_S3_MULTI_VERSION_XML):
        assert pmc_s3_prefix("PMC13242597") == "PMC13242597.10/"


def test_pmc_s3_prefix_returns_none_on_bad_xml():
    with patch("cv.fetch_pmc_figures._get", return_value=b"not xml"):
        assert pmc_s3_prefix("PMC13242597") is None


def test_fetch_pmc_figures_parses_fig_elements():
    with patch("cv.fetch_pmc_figures._get", return_value=_ARTICLE_XML):
        figures = fetch_pmc_figures("PMC13242597")
    assert figures == [
        {
            "label": "Figure 1",
            "caption": "CT scan showing bilateral pleural effusion.",
            "img_ref": "fig1.jpg",
            "figure_type": "imaging",
        }
    ]


def test_fetch_pmc_figures_returns_empty_list_on_bad_xml():
    with patch("cv.fetch_pmc_figures._get", return_value=b"not xml"):
        assert fetch_pmc_figures("PMC13242597") == []
