# SPDX-FileCopyrightText: 2026 California Institute of Technology ("Caltech")
# SPDX-License-Identifier: Apache-2.0
# Part of opera-vlm, https://github.com/mgovorcin/opera-vlm.
"""Run one SAS job from a resolved `Workflow`."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from opera_vlm._log import get_max_memory_usage, log_runtime
from opera_vlm.config import Workflow
from opera_vlm.errors import AlgorithmError, ProductError, SasError

logger = logging.getLogger(__name__)


@log_runtime
def run(workflow: Workflow, pge_runconfig: str | None = None) -> Path:
    """Run the algorithm, write the product and its browse image.

    Logging is configured by the caller (the CLI), so this is also usable
    from notebooks and tests.

    Parameters
    ----------
    workflow : Workflow
        Resolved configuration (`RunConfig.to_workflow`).
    pge_runconfig : str, optional
        Text of the runconfig YAML as run, embedded in the product.

    Returns
    -------
    Path
        The product file.

    """
    from opera_vlm.algorithm import run_algorithm
    from opera_vlm.product import LAYERS, write_product
    from opera_vlm.product._browse import make_browse_image

    processing_start = datetime.now(timezone.utc)
    scratch_existed = workflow.work_directory.exists()
    workflow.create_directories()

    try:
        result = run_algorithm(workflow)
    except SasError:
        raise
    except Exception as e:
        raise AlgorithmError(f"Algorithm failed: {e}") from e

    product = write_product(workflow, result, pge_runconfig, processing_start)
    try:
        png = make_browse_image(product, LAYERS[0].name, product.with_suffix(".png"))
        logger.info("Browse image: %s", png)
    except Exception as e:
        raise ProductError(f"Browse image failed: {e}") from e

    # Only remove a scratch directory this run created: never a user directory
    if not workflow.keep_scratch and not scratch_existed:
        shutil.rmtree(workflow.work_directory, ignore_errors=True)

    logger.info("Product: %s", product)
    logger.info("Maximum memory usage: %.2f GB", get_max_memory_usage(units="GB"))
    return product
